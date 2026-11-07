"""Clúster real en localhost sobre etcd real: servidores de metadatos y nodos de datos juntos.

Cubre lo que cierra la etapa 4: los nodos de datos se dan de alta solos, una carga completa pasa por
WriteBlock con reenvío y se confirma con los avisos reales, y tirar el líder no pierde ninguna confirmación.
"""

import hashlib
import os
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import grpc
import pytest
from helpers import expect_error, start_on_free_addr, wait_until

from dfsha.common.errors import DfshaError, Reason
from dfsha.datanode.block_store import initialize_data_directory
from dfsha.datanode.server import DataNodeConfig, DataNodeServer
from dfsha.datanode.server import create_server as create_datanode
from dfsha.datanode.service import CHUNK_SIZE_BYTES, DataNodeSettings
from dfsha.metadata.server import MetadataConfig, MetadataServer
from dfsha.metadata.server import create_server as create_metadata
from dfsha.metadata.service import MetadataSettings
from dfsha.v1 import common_pb2, datanode_pb2, datanode_pb2_grpc, metadata_pb2, metadata_pb2_grpc

BLOCK_SIZE_BYTES = 1024 * 1024
WHOLE_FILE = common_pb2.BlockRange(first_block_index=0, block_count=0)


def _request_id() -> str:
    return str(uuid.uuid4())


@dataclass
class LocalCluster:
    etcd_addr: str
    prefix: bytes
    tmp_path: Path
    metadata: dict[str, MetadataServer] = field(default_factory=dict)
    datanodes: list[DataNodeServer] = field(default_factory=list)
    channels: dict[str, grpc.Channel] = field(default_factory=dict)

    def start_metadata(self) -> str:
        def start(addr: str) -> tuple[str, MetadataServer]:
            config = MetadataConfig(
                settings=MetadataSettings(addr=addr, block_size_bytes=BLOCK_SIZE_BYTES),
                etcd_addrs=[self.etcd_addr], key_prefix=self.prefix,
                leader_ttl_s=2, leader_refresh_interval_s=0.2, leader_step_down_after_s=1.4,
                suspect_after_s=9, dead_after_s=30, server_threads=8, log_level="INFO",
            )  # fmt: skip
            return addr, create_metadata(config)

        addr, server = start_on_free_addr(start)
        server.start()
        self.metadata[addr] = server
        return addr

    def start_datanode(self, index: int) -> DataNodeServer:
        data_directory = self.tmp_path / f"datanode-{index}"
        data_directory.mkdir()
        initialize_data_directory(data_directory, f"datanode-{index}")

        def start(addr: str) -> DataNodeServer:
            config = DataNodeConfig(
                settings=DataNodeSettings(node_id=f"datanode-{index}", addr=addr, block_size_bytes=BLOCK_SIZE_BYTES),
                data_directory=data_directory, require_mount_point=False, initialize_data_directory=False,
                server_threads=8, log_level="INFO", metadata_addrs=list(self.metadata), heartbeat_interval_s=0.3,
            )  # fmt: skip
            return create_datanode(config)

        server = start_on_free_addr(start)
        server.start()
        self.datanodes.append(server)
        return server

    def get_leader(self) -> str:
        leaders = [addr for addr, server in self.metadata.items() if server.election.is_leader]
        assert len(leaders) == 1, f"líderes: {leaders}"
        return leaders[0]

    def stub(self, addr: str) -> metadata_pb2_grpc.MetadataServiceStub:
        channel = self.channels.setdefault(addr, grpc.insecure_channel(addr))
        return metadata_pb2_grpc.MetadataServiceStub(channel)

    def datanode_stub(self, addr: str) -> datanode_pb2_grpc.DataNodeServiceStub:
        channel = self.channels.setdefault(addr, grpc.insecure_channel(addr))
        return datanode_pb2_grpc.DataNodeServiceStub(channel)

    def call_leader(self, operation: Callable[[metadata_pb2_grpc.MetadataServiceStub], object]) -> object:
        """Como hará el cliente: si responde un seguidor, repite en el líder que indica."""
        addr = next(iter(self.metadata))
        for _ in range(10):
            try:
                return operation(self.stub(addr))
            except grpc.RpcError as rpc_error:
                error = DfshaError.from_rpc_error(rpc_error)
                if error.reason is not Reason.NODE_NOT_LEADER or not error.metadata.get("leader_addr"):
                    raise
                addr = error.metadata["leader_addr"]
        raise AssertionError("demasiadas redirecciones")

    def put(self, path: str, data: bytes) -> int:
        """Carga completa de §6.1 con los RPC reales: abrir, arrendar, reservar, enviar y confirmar."""
        stub = self.stub(self.get_leader())
        opened = stub.OpenFile(metadata_pb2.OpenFileRequest(path=path, mode=metadata_pb2.OPEN_MODE_CREATE), timeout=5)
        lease = stub.LockBlocks(
            metadata_pb2.LockBlocksRequest(request_id=_request_id(), file_handle=opened.file_handle, block_range=WHOLE_FILE),
            timeout=5,
        )
        pieces = [data[offset : offset + BLOCK_SIZE_BYTES] for offset in range(0, len(data), BLOCK_SIZE_BYTES)]
        allocated = stub.AllocateBlocks(
            metadata_pb2.AllocateBlocksRequest(
                request_id=_request_id(), file_handle=opened.file_handle, lease_id=lease.lease_id,
                block_indices=list(range(len(pieces))),
            ),
            timeout=5,
        )  # fmt: skip
        committed = []
        for location, piece in zip(allocated.blocks, pieces, strict=True):
            sha256 = hashlib.sha256(piece).digest()
            primary, *secondaries = location.datanode_addrs
            stored = self.datanode_stub(primary).WriteBlock(_write_requests(location.block_id, piece, sha256, secondaries), timeout=10)
            assert len(stored.stored_on) >= 2
            committed.append(
                metadata_pb2.CommittedBlock(
                    block_index=location.block_index, block_id=location.block_id, block_sha256=sha256, size_bytes=len(piece)
                )
            )
        version = stub.CommitFile(
            metadata_pb2.CommitFileRequest(
                request_id=_request_id(), file_handle=opened.file_handle, lease_id=lease.lease_id,
                write_mode=common_pb2.WRITE_MODE_CREATE, blocks=committed, size_bytes=len(data),
            ),
            timeout=5,
        ).version  # fmt: skip
        stub.UnlockBlocks(metadata_pb2.UnlockBlocksRequest(request_id=_request_id(), lease_id=lease.lease_id), timeout=5)
        return version

    def get(self, path: str) -> bytes:
        """Recuperación de §6.2: abrir, ubicar y leer cada bloque de una réplica."""
        opened = self.call_leader(
            lambda stub: stub.OpenFile(metadata_pb2.OpenFileRequest(path=path, mode=metadata_pb2.OPEN_MODE_READ), timeout=5)
        )
        assert isinstance(opened, metadata_pb2.OpenFileResponse)
        located = self.call_leader(
            lambda stub: stub.GetBlockLocations(
                metadata_pb2.GetBlockLocationsRequest(file_handle=opened.file_handle, block_range=WHOLE_FILE), timeout=5
            )
        )
        assert isinstance(located, metadata_pb2.GetBlockLocationsResponse)
        pieces = []
        for location in located.locations:
            responses = self.datanode_stub(location.datanode_addrs[0]).ReadBlock(
                datanode_pb2.ReadBlockRequest(block_id=location.block_id), timeout=10
            )
            next(responses)  # cabecera
            piece = b"".join(response.data for response in responses)
            assert hashlib.sha256(piece).digest() == location.block_sha256  # el hash de los metadatos, no el del nodo
            pieces.append(piece)
        return b"".join(pieces)[: opened.info.size_bytes]

    def stop(self) -> None:
        for channel in self.channels.values():
            channel.close()
        for datanode in self.datanodes:
            datanode.stop()
        for server in self.metadata.values():
            server.stop()


def _write_requests(block_id: str, data: bytes, sha256: bytes, secondaries: list[str]) -> Iterator[datanode_pb2.WriteBlockRequest]:
    header = datanode_pb2.WriteBlockHeader(block_id=block_id, block_sha256=sha256, size_bytes=len(data), secondary_addrs=secondaries)
    yield datanode_pb2.WriteBlockRequest(header=header)
    for offset in range(0, len(data), CHUNK_SIZE_BYTES):
        yield datanode_pb2.WriteBlockRequest(data=data[offset : offset + CHUNK_SIZE_BYTES])


@pytest.fixture
def cluster(etcd_addr: str, etcd_prefix: bytes, tmp_path: Path) -> Iterator[LocalCluster]:
    local = LocalCluster(etcd_addr, etcd_prefix, tmp_path)
    try:
        for _ in range(3):
            local.start_metadata()
        assert wait_until(lambda: sum(server.election.is_leader for server in local.metadata.values()) == 1)
        for index in range(1, 4):
            local.start_datanode(index)
        assert wait_until(
            lambda: all(d.metadata_client is not None and d.metadata_client.is_registered for d in local.datanodes)
        )
        yield local
    finally:
        local.stop()


def test_put_and_get_through_real_datanodes(cluster: LocalCluster) -> None:
    data = os.urandom(2 * BLOCK_SIZE_BYTES + 12345)
    assert cluster.put("/datos.bin", data) == 1
    assert cluster.get("/datos.bin") == data


def test_leader_crash_loses_no_committed_write(cluster: LocalCluster) -> None:
    files = {f"/antes-{index}.bin": os.urandom(BLOCK_SIZE_BYTES // 2 + index) for index in range(5)}
    for path, data in files.items():
        cluster.put(path, data)
    old_leader = cluster.get_leader()
    old_epoch = cluster.metadata[old_leader].election.epoch
    cluster.metadata.pop(old_leader).stop(resign=False)  # caída: sin liberar la clave del líder
    assert wait_until(lambda: sum(server.election.is_leader for server in cluster.metadata.values()) == 1, timeout_s=10)
    new_leader = cluster.get_leader()
    assert cluster.metadata[new_leader].election.epoch > old_epoch
    # Los nodos de datos encuentran al nuevo líder y vuelven a contar como vivos
    assert wait_until(
        lambda: all(d.metadata_client is not None and d.metadata_client.max_leader_epoch > old_epoch for d in cluster.datanodes),
        timeout_s=10,
    )
    for path, data in files.items():
        assert cluster.get(path) == data  # ninguna confirmación perdida (G1)
    after = os.urandom(BLOCK_SIZE_BYTES)
    assert cluster.put("/despues.bin", after) == 1
    assert cluster.get("/despues.bin") == after


def test_datanode_ignores_commands_from_a_deposed_leader(cluster: LocalCluster) -> None:
    client = cluster.datanodes[0].metadata_client
    assert client is not None and wait_until(lambda: client.max_leader_epoch > 0)
    current = client.max_leader_epoch
    stale_report = metadata_pb2.DataNodeCommand(type=metadata_pb2.DATA_NODE_COMMAND_TYPE_SEND_BLOCK_REPORT)
    executed_before = len(client.executed_commands)
    client.handle_commands(current - 1, [stale_report])
    assert len(client.executed_commands) == executed_before  # orden de un líder depuesto: descartada
    client.handle_commands(current, [stale_report])
    assert len(client.executed_commands) == executed_before + 1


def test_follower_redirects_to_the_leader(cluster: LocalCluster) -> None:
    follower = next(addr for addr, server in cluster.metadata.items() if not server.election.is_leader)
    error = expect_error(lambda: cluster.stub(follower).ListDirectory(metadata_pb2.ListDirectoryRequest(path="/"), timeout=5))
    assert error.reason is Reason.NODE_NOT_LEADER
    assert error.metadata["leader_addr"] == cluster.get_leader()
