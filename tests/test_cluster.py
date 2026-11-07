"""Clúster real en localhost sobre etcd real: servidores de metadatos y nodos de datos juntos.

Cubre lo que cierra la etapa 4: los nodos de datos se dan de alta solos, una carga completa pasa por
WriteBlock con reenvío y se confirma con los avisos reales, y tirar el líder no pierde ninguna confirmación.
"""

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from helpers import expect_error, wait_until
from local_cluster import BLOCK_SIZE_BYTES, LocalCluster

from dfsha.common.errors import Reason
from dfsha.datanode.block_store import BlockStore
from dfsha.v1 import metadata_pb2


@pytest.fixture
def cluster(etcd_addr: str, etcd_prefix: bytes, tmp_path: Path, cluster_secrets: Path) -> Iterator[LocalCluster]:
    local = LocalCluster(etcd_addr, etcd_prefix, tmp_path, secrets=cluster_secrets)
    try:
        for _ in range(3):
            local.start_metadata()
        assert wait_until(lambda: sum(server.election.is_leader for server in local.metadata.values()) == 1)
        local.create_test_user()
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
    # Las escrituras esperan al fin del modo seguro, en cuanto cada bloque tiene una réplica con latido (§9.5)
    assert wait_until(lambda: not cluster.metadata[new_leader].service.is_in_safe_mode(), timeout_s=10)
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


def test_garbage_collection_deletes_only_dead_blocks(
    etcd_addr: str, etcd_prefix: bytes, tmp_path: Path, cluster_secrets: Path
) -> None:
    # Periodo de gracia de 1 s e informe de bloques cada segundo para no esperar 10 y 5 min (§9.3)
    local = LocalCluster(etcd_addr, etcd_prefix, tmp_path, secrets=cluster_secrets, grace_period_s=1, block_report_interval_s=1)
    try:
        for _ in range(3):
            local.start_metadata()
        assert wait_until(lambda: sum(server.election.is_leader for server in local.metadata.values()) == 1)
        local.create_test_user()
        for index in range(1, 4):
            local.start_datanode(index)
        assert wait_until(lambda: all(d.metadata_client is not None and d.metadata_client.is_registered for d in local.datanodes))

        def stored() -> set[str]:
            return {meta.block_id for index in (1, 2, 3) for meta in BlockStore(tmp_path / f"datanode-{index}").list_blocks()}

        kept = os.urandom(BLOCK_SIZE_BYTES + 100)
        local.put("/vivo.bin", kept)
        live_blocks = stored()
        local.put("/abortado.bin", os.urandom(BLOCK_SIZE_BYTES // 2), commit=False)  # bloques huérfanos
        local.put("/borrado.bin", os.urandom(BLOCK_SIZE_BYTES // 2))
        local.call_leader(lambda stub: stub.DeleteFile(metadata_pb2.DeleteFileRequest(request_id=str(uuid.uuid4()), path="/borrado.bin"), timeout=5))
        assert len(stored()) > len(live_blocks)

        # Los huérfanos y la versión borrada, pasado el periodo de gracia, desaparecen de los tres nodos
        assert wait_until(lambda: stored() == live_blocks, timeout_s=10)
        assert local.get("/vivo.bin") == kept
    finally:
        local.stop()
