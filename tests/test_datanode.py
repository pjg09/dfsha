"""Tres nodos de datos reales en localhost: reenvío desde la primaria, quórum W = 2 e integridad."""

import hashlib
import os
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import grpc
import pytest

from dfsha.common.errors import DfshaError, Reason
from helpers import get_free_addr, start_on_free_addr
from dfsha.datanode.block_store import BlockStore, initialize_data_directory
from dfsha.datanode.server import DataNodeConfig, create_server
from dfsha.datanode.service import CHUNK_SIZE_BYTES, DataNodeSettings
from dfsha.v1 import datanode_pb2, datanode_pb2_grpc, metadata_pb2

BLOCK_SIZE_BYTES = 4 * 1024 * 1024


class RecordingReporter:
    def __init__(self) -> None:
        self.blocks: list[metadata_pb2.StoredBlock] = []

    def report_block_received(self, block: metadata_pb2.StoredBlock) -> None:
        self.blocks.append(block)


@dataclass
class Node:
    addr: str
    data_directory: Path
    reporter: RecordingReporter
    server: grpc.Server
    channel: grpc.Channel

    @property
    def stub(self) -> datanode_pb2_grpc.DataNodeServiceStub:
        return datanode_pb2_grpc.DataNodeServiceStub(self.channel)

    def has_block(self, block_id: str) -> bool:
        try:
            BlockStore(self.data_directory).get_block(block_id)
        except DfshaError:
            return False
        return True


@pytest.fixture
def nodes(tmp_path: Path) -> Iterator[list[Node]]:
    started: list[Node] = []
    for index in range(1, 4):
        data_directory = tmp_path / f"datanode-{index}"
        data_directory.mkdir()
        initialize_data_directory(data_directory, f"datanode-{index}")
        reporter = RecordingReporter()

        def start(addr: str, index: int = index, data_directory: Path = data_directory, reporter: RecordingReporter = reporter) -> tuple[str, grpc.Server]:
            node_config = DataNodeConfig(
                settings=DataNodeSettings(
                    node_id=f"datanode-{index}", addr=addr, block_size_bytes=BLOCK_SIZE_BYTES, transfer_timeout_s=10
                ),
                data_directory=data_directory,
                require_mount_point=False,
                initialize_data_directory=False,
                server_threads=8,
                log_level="INFO",
            )
            return addr, create_server(node_config, reporter).server

        addr, server = start_on_free_addr(start)
        server.start()
        started.append(Node(addr, data_directory, reporter, server, grpc.insecure_channel(addr)))
    yield started
    for node in started:
        node.channel.close()
        node.server.stop(grace=None)


def _write_requests(
    block_id: str, data: bytes, secondary_addrs: list[str], sha256: bytes | None = None, size_bytes: int | None = None
) -> Iterator[datanode_pb2.WriteBlockRequest]:
    header = datanode_pb2.WriteBlockHeader(
        block_id=block_id,
        block_sha256=sha256 if sha256 is not None else hashlib.sha256(data).digest(),
        size_bytes=size_bytes if size_bytes is not None else len(data),
        secondary_addrs=secondary_addrs,
    )
    yield datanode_pb2.WriteBlockRequest(header=header)
    for offset in range(0, len(data), CHUNK_SIZE_BYTES):
        yield datanode_pb2.WriteBlockRequest(data=data[offset : offset + CHUNK_SIZE_BYTES])


def _read(node: Node, block_id: str) -> tuple[datanode_pb2.ReadBlockHeader, bytes]:
    responses = node.stub.ReadBlock(datanode_pb2.ReadBlockRequest(block_id=block_id), timeout=10)
    header = next(responses).header
    return header, b"".join(response.data for response in responses)


def _expect_error(call: object) -> DfshaError:
    assert callable(call)
    with pytest.raises(grpc.RpcError) as raised:
        call()
    return DfshaError.from_rpc_error(raised.value)


def _wait_until(condition: object, timeout_s: float = 5) -> bool:
    assert callable(condition)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return False


def test_primary_forwards_to_both_secondaries(nodes: list[Node]) -> None:
    primary, *secondaries = nodes
    data = os.urandom(2 * CHUNK_SIZE_BYTES + 12345)
    block_id = str(uuid.uuid4())
    response = primary.stub.WriteBlock(_write_requests(block_id, data, [n.addr for n in secondaries]), timeout=10)
    assert primary.addr in response.stored_on
    assert len(response.stored_on) >= 2
    assert _wait_until(lambda: all(node.has_block(block_id) for node in nodes)), "la tercera réplica no llegó"
    for node in nodes:
        header, received = _read(node, block_id)
        assert received == data
        assert header.block_sha256 == hashlib.sha256(data).digest()
        assert [block.block_id for block in node.reporter.blocks] == [block_id]


def test_corrupt_block_is_rejected_everywhere(nodes: list[Node]) -> None:
    primary, *secondaries = nodes
    block_id = str(uuid.uuid4())
    requests = _write_requests(block_id, os.urandom(CHUNK_SIZE_BYTES), [n.addr for n in secondaries], sha256=bytes(32))
    error = _expect_error(lambda: primary.stub.WriteBlock(requests, timeout=10))
    assert (error.code, error.reason) == (grpc.StatusCode.ABORTED, Reason.BLOCK_CORRUPTED)
    time.sleep(0.5)
    assert not any(node.has_block(block_id) for node in nodes)
    assert not any(node.reporter.blocks for node in nodes)


def test_quorum_with_one_secondary_down(nodes: list[Node]) -> None:
    primary, secondary, _ = nodes
    block_id = str(uuid.uuid4())
    response = primary.stub.WriteBlock(_write_requests(block_id, b"datos" * 1000, [secondary.addr, get_free_addr()]), timeout=10)
    assert sorted(response.stored_on) == sorted([primary.addr, secondary.addr])


def test_quorum_not_reached_with_both_secondaries_down(nodes: list[Node]) -> None:
    primary = nodes[0]
    requests = _write_requests(str(uuid.uuid4()), b"datos" * 1000, [get_free_addr(), get_free_addr()])
    error = _expect_error(lambda: primary.stub.WriteBlock(requests, timeout=10))
    assert (error.code, error.reason) == (grpc.StatusCode.UNAVAILABLE, Reason.QUORUM_NOT_REACHED)


def test_truncated_stream_is_discarded(nodes: list[Node]) -> None:
    node = nodes[0]
    data = os.urandom(1000)
    block_id = str(uuid.uuid4())
    requests = _write_requests(block_id, data, [], size_bytes=len(data) + 1)
    error = _expect_error(lambda: node.stub.WriteBlock(requests, timeout=10))
    assert error.reason is Reason.BLOCK_CORRUPTED
    assert not node.has_block(block_id)


def test_header_must_come_first(nodes: list[Node]) -> None:
    requests = iter([datanode_pb2.WriteBlockRequest(data=b"x")])
    error = _expect_error(lambda: nodes[0].stub.WriteBlock(requests, timeout=10))
    assert error.code is grpc.StatusCode.INVALID_ARGUMENT


def test_block_larger_than_maximum_is_refused(nodes: list[Node]) -> None:
    requests = _write_requests(str(uuid.uuid4()), b"", [], size_bytes=BLOCK_SIZE_BYTES * 2)
    error = _expect_error(lambda: nodes[0].stub.WriteBlock(requests, timeout=10))
    assert error.code is grpc.StatusCode.INVALID_ARGUMENT


def test_corrupt_replica_on_disk_is_detected_when_read(nodes: list[Node]) -> None:
    node = nodes[0]
    data = os.urandom(CHUNK_SIZE_BYTES + 10)
    block_id = str(uuid.uuid4())
    node.stub.WriteBlock(_write_requests(block_id, data, []), timeout=10)
    path, _ = BlockStore(node.data_directory).get_block(block_id)
    damaged = bytearray(path.read_bytes())
    damaged[100] ^= 0xFF
    path.write_bytes(bytes(damaged))
    error = _expect_error(lambda: _read(node, block_id))
    assert (error.code, error.reason) == (grpc.StatusCode.DATA_LOSS, Reason.BLOCK_CORRUPTED)


def test_missing_block(nodes: list[Node]) -> None:
    error = _expect_error(lambda: _read(nodes[0], str(uuid.uuid4())))
    assert error.code is grpc.StatusCode.NOT_FOUND
