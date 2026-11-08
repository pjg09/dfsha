"""Órdenes de re-replicación del líder (fase I §9.3, ADR 0048), con un servicio mínimo y un reloj falso."""

import time
from types import SimpleNamespace
from typing import Any, cast

from dfsha.metadata.keys import Keys
from dfsha.metadata.nodes import NodeRegistry
from dfsha.metadata.replication import REPLICATION_TIMEOUT_S, ReplicationManager
from dfsha.v1 import metadata_pb2
from dfsha.v1.records_pb2 import NodeRecord, ReplicaRecord, VersionRecord

BLOCK = 16 * 1024 * 1024
SHA = b"\x01" * 32
KEYS = Keys()


class _FakeEtcd:
    def __init__(self, items: dict[bytes, bytes]) -> None:
        self.items = items

    def get_prefix(self, prefix: bytes, revision: int = 0) -> tuple[list[SimpleNamespace], int]:
        kvs = [SimpleNamespace(key=key, value=value) for key, value in sorted(self.items.items()) if key.startswith(prefix)]
        return kvs, 1


def _setup(holders: list[str], nodes: dict[str, int]) -> tuple[ReplicationManager, NodeRegistry, list[float]]:
    """Un bloque vivo con réplicas en ``holders``; ``nodes`` da el espacio libre de cada nodo registrado."""
    now = [1000.0]
    registry = NodeRegistry(suspect_after_s=9, dead_after_s=30, clock=lambda: now[0])
    for node_id, free in nodes.items():
        registry.register(NodeRecord(node_id=node_id, addr=f"{node_id}:50052"), free)
    version = VersionRecord(version=1, blocks=[metadata_pb2.CommittedBlock(block_index=0, block_id="b1", block_sha256=SHA)])
    items = {KEYS.version("f1", 1): version.SerializeToString()}
    for node_id in holders:
        items[KEYS.replica("b1", node_id)] = ReplicaRecord(node_id=node_id, block_sha256=SHA).SerializeToString()
    service = SimpleNamespace(
        registry=registry,
        keys=KEYS,
        store=SimpleNamespace(etcd=_FakeEtcd(items)),
        settings=SimpleNamespace(replication_factor=3),
        _security=SimpleNamespace(block_token_key=b"k" * 32),
        _now=time.time,
        _apply_without_request=lambda *_: None,
    )
    return ReplicationManager(cast(Any, service), clock=lambda: now[0]), registry, now


def _copies(manager: ReplicationManager, node_ids: list[str]) -> list[tuple[str, str]]:
    """(origen, destino) de las órdenes REPLICATE en cola."""
    return [
        (node_id, command.target_addr.partition(":")[0])
        for node_id in node_ids
        for command in manager.pop_commands(node_id)
        if command.type == metadata_pb2.DATA_NODE_COMMAND_TYPE_REPLICATE
    ]


def test_a_node_without_a_recent_heartbeat_is_not_a_copy_target() -> None:
    # escenario 2 en AWS (2026-11-08): el nodo recién parado tenía más espacio libre y seguía vivo para el líder
    manager, registry, now = _setup(["datanode-1", "datanode-2"], {"datanode-1": BLOCK, "datanode-2": BLOCK, "datanode-3": 100 * BLOCK, "datanode-4": 10 * BLOCK})
    now[0] += 5  # datanode-3 no envía latidos desde hace 5 s: sigue vivo (sospechoso a los 9 s)
    for node_id in ("datanode-1", "datanode-2", "datanode-4"):
        registry.record_heartbeat(node_id, 10 * BLOCK if node_id == "datanode-4" else BLOCK)
    manager.run_pass()
    copies = _copies(manager, ["datanode-1", "datanode-2", "datanode-3", "datanode-4"])
    assert [target for _, target in copies] == ["datanode-4"]


def test_a_node_without_a_recent_heartbeat_is_not_a_copy_source() -> None:
    # Las órdenes viajan en la respuesta al latido: un origen que no envía latidos nunca la recibe
    manager, registry, now = _setup(["datanode-1", "datanode-2"], {"datanode-1": BLOCK, "datanode-2": BLOCK, "datanode-3": 10 * BLOCK})
    now[0] += 5
    for node_id in ("datanode-2", "datanode-3"):
        registry.record_heartbeat(node_id, 10 * BLOCK if node_id == "datanode-3" else BLOCK)
    manager.run_pass()
    assert _copies(manager, ["datanode-1", "datanode-2", "datanode-3"]) == [("datanode-2", "datanode-3")]


def test_a_copy_that_does_not_arrive_is_ordered_again_after_the_timeout() -> None:
    manager, registry, now = _setup(["datanode-1", "datanode-2"], {"datanode-1": BLOCK, "datanode-2": BLOCK, "datanode-3": 10 * BLOCK})
    manager.run_pass()
    assert _copies(manager, ["datanode-1", "datanode-2"]) == [("datanode-1", "datanode-3")]
    for elapsed in (3.0, REPLICATION_TIMEOUT_S - 1):  # la copia está en curso: no se repite
        now[0] = 1000.0 + elapsed
        for node_id in ("datanode-1", "datanode-2", "datanode-3"):
            registry.record_heartbeat(node_id, BLOCK)
        manager.run_pass()
        assert _copies(manager, ["datanode-1", "datanode-2"]) == []
    now[0] = 1000.0 + REPLICATION_TIMEOUT_S + 1  # sin aviso de bloque recibido: se vuelve a ordenar
    for node_id in ("datanode-1", "datanode-2", "datanode-3"):
        registry.record_heartbeat(node_id, BLOCK)
    manager.run_pass()
    assert len(_copies(manager, ["datanode-1", "datanode-2"])) == 1
    assert REPLICATION_TIMEOUT_S == 15.0
