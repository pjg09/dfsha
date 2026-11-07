"""Servidor de metadatos real sobre etcd real: espacio de nombres, carga, arrendamientos y versiones."""

import hashlib
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass

import grpc
import pytest
from helpers import expect_error, start_on_free_addr, wait_until

from dfsha.common.errors import Reason
from dfsha.metadata.server import MetadataConfig, MetadataServer, create_server
from dfsha.metadata.service import MetadataSettings
from dfsha.v1 import common_pb2, metadata_pb2, metadata_pb2_grpc

BLOCK_SIZE_BYTES = 1024 * 1024
WHOLE_FILE = common_pb2.BlockRange(first_block_index=0, block_count=0)


def _request_id() -> str:
    return str(uuid.uuid4())


@dataclass
class Cluster:
    server: MetadataServer
    stub: metadata_pb2_grpc.MetadataServiceStub
    addr: str

    def register_nodes(self, count: int) -> list[str]:
        node_ids = [f"datanode-{n}" for n in range(1, count + 1)]
        for node_id in node_ids:
            self.stub.RegisterDataNode(
                metadata_pb2.RegisterDataNodeRequest(
                    node_id=node_id, hostname=node_id, addr=f"{node_id}:50052", capacity_bytes=10**10, free_bytes=10**10
                ),
                timeout=5,
            )
        return node_ids

    def report_replicas(self, block: common_pb2.BlockLocation, data: bytes, copies: int) -> None:
        for addr in block.datanode_addrs[:copies]:
            self.stub.ReportBlockReceived(
                metadata_pb2.ReportBlockReceivedRequest(
                    node_id=addr.split(":")[0],
                    block=metadata_pb2.StoredBlock(
                        block_id=block.block_id, block_sha256=hashlib.sha256(data).digest(), size_bytes=len(data)
                    ),
                ),
                timeout=5,
            )

    def put(self, path: str, blocks: list[bytes], copies: int = 2) -> int:
        """Carga completa como en §6.1, con los avisos de bloque recibido simulados."""
        opened = self.stub.OpenFile(metadata_pb2.OpenFileRequest(path=path, mode=metadata_pb2.OPEN_MODE_CREATE), timeout=5)
        lease = self.stub.LockBlocks(
            metadata_pb2.LockBlocksRequest(request_id=_request_id(), file_handle=opened.file_handle, block_range=WHOLE_FILE),
            timeout=5,
        )
        committed = self.write_blocks(opened.file_handle, lease.lease_id, list(enumerate(blocks)), copies)
        response = self.stub.CommitFile(
            metadata_pb2.CommitFileRequest(
                request_id=_request_id(),
                file_handle=opened.file_handle,
                lease_id=lease.lease_id,
                write_mode=common_pb2.WRITE_MODE_CREATE,
                blocks=committed,
                size_bytes=sum(len(block) for block in blocks),
            ),
            timeout=5,
        )
        self.stub.UnlockBlocks(metadata_pb2.UnlockBlocksRequest(request_id=_request_id(), lease_id=lease.lease_id), timeout=5)
        return response.version

    def write_blocks(
        self, file_handle: bytes, lease_id: str, blocks: list[tuple[int, bytes]], copies: int = 2
    ) -> list[metadata_pb2.CommittedBlock]:
        allocated = self.stub.AllocateBlocks(
            metadata_pb2.AllocateBlocksRequest(
                request_id=_request_id(), file_handle=file_handle, lease_id=lease_id, block_indices=[index for index, _ in blocks]
            ),
            timeout=5,
        )
        committed = []
        for location, (_, data) in zip(allocated.blocks, blocks, strict=True):
            self.report_replicas(location, data, copies)
            committed.append(
                metadata_pb2.CommittedBlock(
                    block_index=location.block_index,
                    block_id=location.block_id,
                    block_sha256=hashlib.sha256(data).digest(),
                    size_bytes=len(data),
                )
            )
        return committed

    def ls(self, path: str) -> list[str]:
        return [entry.name for entry in self.stub.ListDirectory(metadata_pb2.ListDirectoryRequest(path=path), timeout=5).entries]

    def mkdir(self, path: str, request_id: str | None = None) -> None:
        self.stub.CreateDirectory(
            metadata_pb2.CreateDirectoryRequest(request_id=request_id or _request_id(), path=path), timeout=5
        )


def _start(etcd_addr: str, prefix: bytes, **overrides: int) -> tuple[MetadataServer, str]:
    def start(addr: str) -> tuple[MetadataServer, str]:
        settings = MetadataSettings(addr=addr, block_size_bytes=BLOCK_SIZE_BYTES, **overrides)
        server = create_server(
            MetadataConfig(
                settings=settings,
                etcd_addrs=[etcd_addr],
                key_prefix=prefix,
                leader_ttl_s=2,
                leader_refresh_interval_s=0.2,
                leader_step_down_after_s=1.4,
                suspect_after_s=9,
                dead_after_s=30,
                server_threads=8,
                log_level="INFO",
            )
        )
        return server, addr

    server, addr = start_on_free_addr(start)
    server.start()
    return server, addr


@pytest.fixture
def make_cluster(etcd_addr: str, etcd_prefix: bytes) -> Iterator[Callable[..., Cluster]]:
    started: list[tuple[MetadataServer, grpc.Channel]] = []

    def make(**overrides: int) -> Cluster:
        server, addr = _start(etcd_addr, etcd_prefix, **overrides)
        channel = grpc.insecure_channel(addr)
        started.append((server, channel))
        assert wait_until(lambda: server.election.is_leader), "el servidor no llegó a ser líder"
        return Cluster(server, metadata_pb2_grpc.MetadataServiceStub(channel), addr)

    yield make
    for server, channel in started:
        channel.close()
        server.stop()


@pytest.fixture
def cluster(make_cluster: Callable[..., Cluster]) -> Cluster:
    created = make_cluster()
    created.register_nodes(5)
    return created


# ===== Espacio de nombres ====================================================================


def test_mkdir_and_ls(cluster: Cluster) -> None:
    cluster.mkdir("/docs")
    cluster.mkdir("/docs/2026")
    assert cluster.ls("/") == ["docs"]
    assert cluster.ls("/docs") == ["2026"]
    error = expect_error(lambda: cluster.mkdir("/docs"))
    assert (error.code, error.reason) == (grpc.StatusCode.ALREADY_EXISTS, Reason.PATH_ALREADY_EXISTS)
    error = expect_error(lambda: cluster.mkdir("/no/existe"))
    assert (error.code, error.reason) == (grpc.StatusCode.NOT_FOUND, Reason.PATH_NOT_FOUND)
    error = expect_error(lambda: cluster.mkdir("relativa"))
    assert (error.code, error.reason) == (grpc.StatusCode.INVALID_ARGUMENT, Reason.PATH_INVALID)


def test_retried_mkdir_returns_the_same_response(cluster: Cluster) -> None:
    request_id = _request_id()
    cluster.mkdir("/docs", request_id)
    cluster.mkdir("/docs", request_id)  # reintento tras un plazo vencido: no da ALREADY_EXISTS (§6.5)
    assert cluster.ls("/") == ["docs"]


def test_rmdir_only_empty_directories(cluster: Cluster) -> None:
    cluster.mkdir("/a")
    cluster.mkdir("/a/b")
    error = expect_error(
        lambda: cluster.stub.DeleteDirectory(metadata_pb2.DeleteDirectoryRequest(request_id=_request_id(), path="/a"), timeout=5)
    )
    assert (error.code, error.reason) == (grpc.StatusCode.FAILED_PRECONDITION, Reason.DIRECTORY_NOT_EMPTY)
    cluster.stub.DeleteDirectory(metadata_pb2.DeleteDirectoryRequest(request_id=_request_id(), path="/a/b"), timeout=5)
    cluster.stub.DeleteDirectory(metadata_pb2.DeleteDirectoryRequest(request_id=_request_id(), path="/a"), timeout=5)
    assert cluster.ls("/") == []


def test_mv_of_a_large_directory_is_one_change(cluster: Cluster) -> None:
    cluster.mkdir("/grande")
    for index in range(150):  # más entradas que operaciones caben en una transacción de etcd
        cluster.mkdir(f"/grande/d{index:03d}")
    cluster.mkdir("/destino")
    cluster.stub.MovePath(
        metadata_pb2.MovePathRequest(request_id=_request_id(), source_path="/grande", target_path="/destino/movido"), timeout=5
    )
    assert cluster.ls("/") == ["destino"]
    assert len(cluster.ls("/destino/movido")) == 150


def test_mv_rejects_moving_a_directory_into_itself(cluster: Cluster) -> None:
    cluster.mkdir("/a")
    cluster.mkdir("/a/b")
    error = expect_error(
        lambda: cluster.stub.MovePath(
            metadata_pb2.MovePathRequest(request_id=_request_id(), source_path="/a", target_path="/a/b/c"), timeout=5
        )
    )
    assert (error.code, error.reason) == (grpc.StatusCode.INVALID_ARGUMENT, Reason.PATH_INVALID)


# ===== Carga y lectura =======================================================================


def test_put_then_locations(cluster: Cluster) -> None:
    blocks = [b"a" * 100, b"b" * 100, b"c" * 50]
    assert cluster.put("/datos.bin", blocks) == 1
    info = cluster.stub.GetFileInfo(metadata_pb2.GetFileInfoRequest(path="/datos.bin"), timeout=5).info
    assert (info.version, info.size_bytes) == (1, 250)
    opened = cluster.stub.OpenFile(metadata_pb2.OpenFileRequest(path="/datos.bin", mode=metadata_pb2.OPEN_MODE_READ), timeout=5)
    locations = cluster.stub.GetBlockLocations(
        metadata_pb2.GetBlockLocationsRequest(file_handle=opened.file_handle, block_range=WHOLE_FILE), timeout=5
    ).locations
    assert [location.block_index for location in locations] == [0, 1, 2]
    for location, data in zip(locations, blocks, strict=True):
        assert location.block_sha256 == hashlib.sha256(data).digest()
        assert len(location.datanode_addrs) == 2  # las dos réplicas que avisaron
    assert cluster.ls("/") == ["datos.bin"]


def test_allocation_spreads_blocks_over_distinct_nodes(cluster: Cluster) -> None:
    opened = cluster.stub.OpenFile(metadata_pb2.OpenFileRequest(path="/x", mode=metadata_pb2.OPEN_MODE_CREATE), timeout=5)
    lease = cluster.stub.LockBlocks(
        metadata_pb2.LockBlocksRequest(request_id=_request_id(), file_handle=opened.file_handle, block_range=WHOLE_FILE), timeout=5
    )
    allocated = cluster.stub.AllocateBlocks(
        metadata_pb2.AllocateBlocksRequest(
            request_id=_request_id(), file_handle=opened.file_handle, lease_id=lease.lease_id, block_indices=list(range(10))
        ),
        timeout=5,
    )
    used_nodes = set()
    primaries = set()
    for block in allocated.blocks:
        assert len(block.datanode_addrs) == 3
        assert len(set(block.datanode_addrs)) == 3  # nunca dos réplicas en el mismo nodo
        used_nodes.update(block.datanode_addrs)
        primaries.add(block.datanode_addrs[0])
    assert len(used_nodes) == 5  # los bloques se reparten entre los cinco nodos
    assert len(primaries) > 1  # la primaria rota


def test_commit_needs_write_quorum(cluster: Cluster) -> None:
    opened = cluster.stub.OpenFile(metadata_pb2.OpenFileRequest(path="/x", mode=metadata_pb2.OPEN_MODE_CREATE), timeout=5)
    lease = cluster.stub.LockBlocks(
        metadata_pb2.LockBlocksRequest(request_id=_request_id(), file_handle=opened.file_handle, block_range=WHOLE_FILE), timeout=5
    )
    committed = cluster.write_blocks(opened.file_handle, lease.lease_id, [(0, b"datos")], copies=1)
    error = expect_error(
        lambda: cluster.stub.CommitFile(
            metadata_pb2.CommitFileRequest(
                request_id=_request_id(), file_handle=opened.file_handle, lease_id=lease.lease_id,
                write_mode=common_pb2.WRITE_MODE_CREATE, blocks=committed, size_bytes=5,
            ),
            timeout=5,
        )
    )  # fmt: skip
    assert (error.code, error.reason) == (grpc.StatusCode.UNAVAILABLE, Reason.QUORUM_NOT_REACHED)
    assert cluster.ls("/") == []  # nada visible a medias (G4)


def test_commit_refuses_blocks_that_were_not_allocated(cluster: Cluster) -> None:
    opened = cluster.stub.OpenFile(metadata_pb2.OpenFileRequest(path="/x", mode=metadata_pb2.OPEN_MODE_CREATE), timeout=5)
    lease = cluster.stub.LockBlocks(
        metadata_pb2.LockBlocksRequest(request_id=_request_id(), file_handle=opened.file_handle, block_range=WHOLE_FILE), timeout=5
    )
    forged = metadata_pb2.CommittedBlock(block_index=0, block_id=str(uuid.uuid4()), block_sha256=bytes(32), size_bytes=1)
    error = expect_error(
        lambda: cluster.stub.CommitFile(
            metadata_pb2.CommitFileRequest(
                request_id=_request_id(), file_handle=opened.file_handle, lease_id=lease.lease_id,
                write_mode=common_pb2.WRITE_MODE_CREATE, blocks=[forged], size_bytes=1,
            ),
            timeout=5,
        )
    )  # fmt: skip
    assert error.reason is Reason.BLOCK_RANGE_INVALID


def test_allocation_needs_write_quorum_of_live_nodes(make_cluster: Callable[..., Cluster]) -> None:
    lonely = make_cluster()
    lonely.register_nodes(1)
    opened = lonely.stub.OpenFile(metadata_pb2.OpenFileRequest(path="/x", mode=metadata_pb2.OPEN_MODE_CREATE), timeout=5)
    lease = lonely.stub.LockBlocks(
        metadata_pb2.LockBlocksRequest(request_id=_request_id(), file_handle=opened.file_handle, block_range=WHOLE_FILE), timeout=5
    )
    error = expect_error(lambda: lonely.write_blocks(opened.file_handle, lease.lease_id, [(0, b"x")]))
    assert (error.code, error.reason) == (grpc.StatusCode.UNAVAILABLE, Reason.QUORUM_NOT_REACHED)


# ===== Arrendamientos y versiones ============================================================


def _open_for_write(cluster: Cluster, path: str) -> bytes:
    return cluster.stub.OpenFile(metadata_pb2.OpenFileRequest(path=path, mode=metadata_pb2.OPEN_MODE_WRITE), timeout=5).file_handle


def _lock(cluster: Cluster, handle: bytes, first: int, count: int) -> metadata_pb2.LockBlocksResponse:
    return cluster.stub.LockBlocks(
        metadata_pb2.LockBlocksRequest(
            request_id=_request_id(), file_handle=handle, block_range=common_pb2.BlockRange(first_block_index=first, block_count=count)
        ),
        timeout=5,
    )


def _commit_partial(cluster: Cluster, handle: bytes, lease_id: str, blocks: list[tuple[int, bytes]], size: int) -> int:
    committed = cluster.write_blocks(handle, lease_id, blocks)
    return cluster.stub.CommitFile(
        metadata_pb2.CommitFileRequest(
            request_id=_request_id(), file_handle=handle, lease_id=lease_id,
            write_mode=common_pb2.WRITE_MODE_PARTIAL, blocks=committed, size_bytes=size,
        ),
        timeout=5,
    ).version  # fmt: skip


def test_overlapping_lease_is_refused_at_once(cluster: Cluster) -> None:
    cluster.put("/datos.bin", [b"0", b"1", b"2", b"3", b"4"])
    first = _open_for_write(cluster, "/datos.bin")
    second = _open_for_write(cluster, "/datos.bin")
    _lock(cluster, first, 3, 1)
    error = expect_error(lambda: _lock(cluster, second, 2, 3))  # escenario 1, §11.1
    assert (error.code, error.reason) == (grpc.StatusCode.ABORTED, Reason.LOCK_CONFLICT)
    _lock(cluster, second, 0, 2)  # rangos que no se solapan: los dos escriben


def test_writers_on_different_blocks_both_commit(cluster: Cluster) -> None:
    cluster.put("/datos.bin", [b"0", b"1", b"2", b"3"])
    first, second = _open_for_write(cluster, "/datos.bin"), _open_for_write(cluster, "/datos.bin")
    first_lease, second_lease = _lock(cluster, first, 0, 1), _lock(cluster, second, 3, 1)
    assert _commit_partial(cluster, first, first_lease.lease_id, [(0, b"A")], 4) == 2
    assert _commit_partial(cluster, second, second_lease.lease_id, [(3, b"D")], 4) == 3  # se aplica sobre la otra (§8.2)


def test_stale_writer_gets_version_conflict(cluster: Cluster) -> None:
    cluster.put("/datos.bin", [b"0", b"1"])
    stale = _open_for_write(cluster, "/datos.bin")  # abre la versión 1
    fresh = _open_for_write(cluster, "/datos.bin")
    lease = _lock(cluster, fresh, 1, 1)
    _commit_partial(cluster, fresh, lease.lease_id, [(1, b"X")], 2)
    cluster.stub.UnlockBlocks(metadata_pb2.UnlockBlocksRequest(request_id=_request_id(), lease_id=lease.lease_id), timeout=5)
    stale_lease = _lock(cluster, stale, 1, 1)
    assert stale_lease.current_version == 2  # la respuesta avisa de que la versión cambió
    error = expect_error(lambda: _commit_partial(cluster, stale, stale_lease.lease_id, [(1, b"Y")], 2))
    assert (error.code, error.reason) == (grpc.StatusCode.ABORTED, Reason.VERSION_CONFLICT)


def test_expired_lease_cannot_commit(make_cluster: Callable[..., Cluster]) -> None:
    short = make_cluster(lease_ttl_s=1)
    short.register_nodes(3)
    opened = short.stub.OpenFile(metadata_pb2.OpenFileRequest(path="/x", mode=metadata_pb2.OPEN_MODE_CREATE), timeout=5)
    lease = short.stub.LockBlocks(
        metadata_pb2.LockBlocksRequest(request_id=_request_id(), file_handle=opened.file_handle, block_range=WHOLE_FILE), timeout=5
    )
    committed = short.write_blocks(opened.file_handle, lease.lease_id, [(0, b"x")])
    time.sleep(1.2)
    error = expect_error(
        lambda: short.stub.CommitFile(
            metadata_pb2.CommitFileRequest(
                request_id=_request_id(), file_handle=opened.file_handle, lease_id=lease.lease_id,
                write_mode=common_pb2.WRITE_MODE_CREATE, blocks=committed, size_bytes=1,
            ),
            timeout=5,
        )
    )  # fmt: skip
    assert (error.code, error.reason) == (grpc.StatusCode.ABORTED, Reason.LEASE_EXPIRED)
    other = short.stub.OpenFile(metadata_pb2.OpenFileRequest(path="/x", mode=metadata_pb2.OPEN_MODE_CREATE), timeout=5)
    short.stub.LockBlocks(  # un arrendamiento caducado no bloquea a nadie
        metadata_pb2.LockBlocksRequest(request_id=_request_id(), file_handle=other.file_handle, block_range=WHOLE_FILE), timeout=5
    )


def test_old_version_readable_during_grace_period(make_cluster: Callable[..., Cluster]) -> None:
    quick = make_cluster(grace_period_s=1)
    quick.register_nodes(3)
    quick.put("/datos.bin", [b"v1"])
    reader = quick.stub.OpenFile(metadata_pb2.OpenFileRequest(path="/datos.bin", mode=metadata_pb2.OPEN_MODE_READ), timeout=5)
    writer = _open_for_write(quick, "/datos.bin")
    lease = _lock(quick, writer, 0, 0)
    committed = quick.write_blocks(writer, lease.lease_id, [(0, b"v2")])
    quick.stub.CommitFile(
        metadata_pb2.CommitFileRequest(
            request_id=_request_id(), file_handle=writer, lease_id=lease.lease_id,
            write_mode=common_pb2.WRITE_MODE_REPLACE, blocks=committed, size_bytes=2,
        ),
        timeout=5,
    )  # fmt: skip
    locate = lambda: quick.stub.GetBlockLocations(  # noqa: E731
        metadata_pb2.GetBlockLocationsRequest(file_handle=reader.file_handle, block_range=WHOLE_FILE), timeout=5
    )
    assert locate().locations[0].block_sha256 == hashlib.sha256(b"v1").digest()  # sigue leyendo su versión (G3)
    time.sleep(1.2)
    error = expect_error(locate)
    assert (error.code, error.reason) == (grpc.StatusCode.FAILED_PRECONDITION, Reason.FILE_VERSION_EXPIRED)


def test_rm(cluster: Cluster) -> None:
    cluster.put("/datos.bin", [b"x"])
    handle = _open_for_write(cluster, "/datos.bin")
    lease = _lock(cluster, handle, 0, 1)
    delete = lambda: cluster.stub.DeleteFile(  # noqa: E731
        metadata_pb2.DeleteFileRequest(request_id=_request_id(), path="/datos.bin"), timeout=5
    )
    error = expect_error(delete)
    assert (error.code, error.reason) == (grpc.StatusCode.ABORTED, Reason.LOCK_CONFLICT)  # no se borra mientras se escribe
    cluster.stub.UnlockBlocks(metadata_pb2.UnlockBlocksRequest(request_id=_request_id(), lease_id=lease.lease_id), timeout=5)
    delete()
    assert cluster.ls("/") == []
    error = expect_error(
        lambda: cluster.stub.OpenFile(metadata_pb2.OpenFileRequest(path="/datos.bin", mode=metadata_pb2.OPEN_MODE_READ), timeout=5)
    )
    assert error.reason is Reason.PATH_NOT_FOUND


# ===== Líder =================================================================================


def test_follower_points_to_the_leader(cluster: Cluster, make_cluster: Callable[..., Cluster], etcd_addr: str, etcd_prefix: bytes) -> None:
    follower, follower_addr = _start(etcd_addr, etcd_prefix)
    try:
        with grpc.insecure_channel(follower_addr) as channel:
            stub = metadata_pb2_grpc.MetadataServiceStub(channel)
            error = expect_error(lambda: stub.ListDirectory(metadata_pb2.ListDirectoryRequest(path="/"), timeout=5))
        assert (error.code, error.reason) == (grpc.StatusCode.UNAVAILABLE, Reason.NODE_NOT_LEADER)
        assert error.metadata["leader_addr"] == cluster.addr
    finally:
        follower.stop()


def test_heartbeat_carries_the_leader_epoch(cluster: Cluster) -> None:
    response = cluster.stub.ReportHeartbeat(metadata_pb2.ReportHeartbeatRequest(node_id="datanode-1", free_bytes=10**9), timeout=5)
    assert response.leader_epoch == cluster.server.election.epoch > 0


def test_update_lease_extends_it(make_cluster: Callable[..., Cluster]) -> None:
    short = make_cluster(lease_ttl_s=1)
    short.register_nodes(3)
    opened = short.stub.OpenFile(metadata_pb2.OpenFileRequest(path="/x", mode=metadata_pb2.OPEN_MODE_CREATE), timeout=5)
    lease = short.stub.LockBlocks(
        metadata_pb2.LockBlocksRequest(request_id=_request_id(), file_handle=opened.file_handle, block_range=WHOLE_FILE), timeout=5
    )
    for _ in range(3):  # renovar antes de que caduque mantiene el arrendamiento más allá de su TTL
        time.sleep(0.6)
        short.stub.UpdateLease(metadata_pb2.UpdateLeaseRequest(request_id=_request_id(), lease_id=lease.lease_id), timeout=5)
    committed = short.write_blocks(opened.file_handle, lease.lease_id, [(0, b"x")])
    short.stub.CommitFile(
        metadata_pb2.CommitFileRequest(
            request_id=_request_id(), file_handle=opened.file_handle, lease_id=lease.lease_id,
            write_mode=common_pb2.WRITE_MODE_CREATE, blocks=committed, size_bytes=1,
        ),
        timeout=5,
    )  # fmt: skip
    time.sleep(1.2)
    error = expect_error(
        lambda: short.stub.UpdateLease(metadata_pb2.UpdateLeaseRequest(request_id=_request_id(), lease_id=lease.lease_id), timeout=5)
    )
    assert (error.code, error.reason) == (grpc.StatusCode.ABORTED, Reason.LEASE_EXPIRED)


def test_abort_discards_the_write_in_progress(cluster: Cluster) -> None:
    opened = cluster.stub.OpenFile(metadata_pb2.OpenFileRequest(path="/x", mode=metadata_pb2.OPEN_MODE_CREATE), timeout=5)
    lease = cluster.stub.LockBlocks(
        metadata_pb2.LockBlocksRequest(request_id=_request_id(), file_handle=opened.file_handle, block_range=WHOLE_FILE), timeout=5
    )
    committed = cluster.write_blocks(opened.file_handle, lease.lease_id, [(0, b"x")])
    cluster.stub.AbortFile(
        metadata_pb2.AbortFileRequest(request_id=_request_id(), file_handle=opened.file_handle, lease_id=lease.lease_id), timeout=5
    )
    error = expect_error(  # los bloques reservados ya no pertenecen a ninguna escritura en curso
        lambda: cluster.stub.CommitFile(
            metadata_pb2.CommitFileRequest(
                request_id=_request_id(), file_handle=opened.file_handle, lease_id=lease.lease_id,
                write_mode=common_pb2.WRITE_MODE_CREATE, blocks=committed, size_bytes=1,
            ),
            timeout=5,
        )
    )  # fmt: skip
    assert error.reason is Reason.BLOCK_RANGE_INVALID
    assert cluster.ls("/") == []
