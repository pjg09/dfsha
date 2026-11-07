"""Tolerancia a fallos con nodos de datos reales: re-replicación, réplicas de más y réplicas corruptas.

Fase I §8.5 y §9.3, con plazos cortos: caído a los 2 s y mantenimiento del líder cada 0,3 s.
"""

import os
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from helpers import wait_until
from local_cluster import BLOCK_SIZE_BYTES, LocalCluster

from dfsha.datanode.block_store import BlockStore
from dfsha.v1 import metadata_pb2

DATANODES = 4


def _start(local: LocalCluster) -> LocalCluster:
    for _ in range(3):
        local.start_metadata()
    assert wait_until(lambda: sum(server.election.is_leader for server in local.metadata.values()) == 1)
    local.create_test_user()
    for index in range(1, DATANODES + 1):
        local.start_datanode(index)
    assert wait_until(lambda: all(d.metadata_client is not None and d.metadata_client.is_registered for d in local.datanodes))
    leader = local.metadata[local.get_leader()]
    assert wait_until(lambda: not leader.service.is_in_safe_mode())
    return local


def _fast(etcd_addr: str, etcd_prefix: bytes, tmp_path: Path, secrets: Path, verify_interval_s: float = 86400) -> LocalCluster:
    return LocalCluster(
        etcd_addr, etcd_prefix, tmp_path, secrets, suspect_after_s=0.5, dead_after_s=2, maintenance_interval_s=0.3,
        verify_interval_s=verify_interval_s,
    )  # fmt: skip


@pytest.fixture
def cluster(etcd_addr: str, etcd_prefix: bytes, tmp_path: Path, cluster_secrets: Path) -> Iterator[LocalCluster]:
    local = _fast(etcd_addr, etcd_prefix, tmp_path, cluster_secrets)
    try:
        yield _start(local)
    finally:
        local.stop()


def _on_disk(local: LocalCluster) -> dict[str, set[int]]:
    """Para cada bloque, los nodos de datos (1 a 4) que tienen una réplica en disco."""
    replicas: dict[str, set[int]] = {}
    for index in range(1, DATANODES + 1):
        for meta in BlockStore(local.tmp_path / f"datanode-{index}").list_blocks():
            replicas.setdefault(meta.block_id, set()).add(index)
    return replicas


def _corrupt(local: LocalCluster, index: int, block_id: str) -> None:
    path = local.tmp_path / f"datanode-{index}" / "blocks" / block_id[:2] / block_id
    data = bytearray(path.read_bytes())
    data[100] ^= 0xFF  # corrupción silenciosa: el disco cambia un byte sin avisar (S2)
    path.write_bytes(bytes(data))


def test_rereplication_after_a_datanode_dies_and_extra_replica_on_return(cluster: LocalCluster) -> None:
    data = os.urandom(2 * BLOCK_SIZE_BYTES + 10)
    cluster.put("/r.bin", data)
    blocks = _on_disk(cluster)
    assert len(blocks) == 3 and all(len(nodes) == 3 for nodes in blocks.values())
    victim = max(range(1, DATANODES + 1), key=lambda index: sum(index in nodes for nodes in blocks.values()))
    cluster.datanodes[victim - 1].stop()  # caído a los 2 s sin latido
    # Cada bloque vuelve a tener 3 réplicas sin contar las del nodo caído
    assert wait_until(lambda: all(len(nodes - {victim}) == 3 for nodes in _on_disk(cluster).values()), timeout_s=15)
    assert cluster.get("/r.bin") == data
    cluster.start_datanode(victim)  # vuelve con sus bloques: ahora sobran réplicas
    assert wait_until(lambda: all(len(nodes) == 3 for nodes in _on_disk(cluster).values()), timeout_s=15)
    assert cluster.get("/r.bin") == data


def test_periodic_verifier_finds_a_corrupt_replica(
    etcd_addr: str, etcd_prefix: bytes, tmp_path: Path, cluster_secrets: Path
) -> None:
    local = _fast(etcd_addr, etcd_prefix, tmp_path, cluster_secrets, verify_interval_s=1)
    try:
        _start(local)
        data = os.urandom(BLOCK_SIZE_BYTES // 2)
        local.put("/c.bin", data)
        [(block_id, nodes)] = _on_disk(local).items()
        damaged = min(nodes)
        _corrupt(local, damaged, block_id)
        # El verificador la encuentra, se re-replica desde una sana y después se borra la corrupta
        assert wait_until(lambda: damaged not in _on_disk(local)[block_id] and len(_on_disk(local)[block_id]) == 3, timeout_s=20)
        assert local.get("/c.bin") == data
    finally:
        local.stop()


def test_client_report_only_triggers_a_verification(cluster: LocalCluster) -> None:
    cluster.put("/v.bin", os.urandom(BLOCK_SIZE_BYTES // 2))
    [(block_id, nodes)] = _on_disk(cluster).items()
    healthy, damaged = sorted(nodes)[:2]

    def report(index: int) -> None:
        addr = cluster.datanodes[index - 1].metadata_client._addr  # type: ignore[union-attr]
        cluster.call_leader(
            lambda stub: stub.ReportCorruptReplica(metadata_pb2.ReportCorruptReplicaRequest(block_id=block_id, node_id=addr), timeout=5)
        )

    report(healthy)  # un cliente avisa de una réplica sana: el nodo la verifica y no pasa nada (§8.5, S5)
    time.sleep(3)
    assert _on_disk(cluster)[block_id] == nodes
    _corrupt(cluster, damaged, block_id)
    report(damaged)  # ahora sí está corrupta: el nodo lo confirma, se re-replica y se borra
    assert wait_until(lambda: damaged not in _on_disk(cluster)[block_id] and len(_on_disk(cluster)[block_id]) == 3, timeout_s=15)
