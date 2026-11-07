"""Clúster real en localhost sobre etcd real, compartido por las pruebas de extremo a extremo."""

import hashlib
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import grpc
from helpers import start_on_free_addr

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
    suspect_after_s: float = 9
    metadata: dict[str, MetadataServer] = field(default_factory=dict)
    datanodes: list[DataNodeServer] = field(default_factory=list)
    channels: dict[str, grpc.Channel] = field(default_factory=dict)

    def start_metadata(self) -> str:
        def start(addr: str) -> tuple[str, MetadataServer]:
            config = MetadataConfig(
                settings=MetadataSettings(addr=addr, block_size_bytes=BLOCK_SIZE_BYTES),
                etcd_addrs=[self.etcd_addr], key_prefix=self.prefix,
                leader_ttl_s=2, leader_refresh_interval_s=0.2, leader_step_down_after_s=1.4,
                suspect_after_s=self.suspect_after_s, dead_after_s=30, server_threads=8, log_level="INFO",
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
