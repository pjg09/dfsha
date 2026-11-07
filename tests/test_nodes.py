"""Registro de nodos de datos y ubicación de réplicas (fase I §4.3 y §9.2)."""

from dfsha.metadata.nodes import NodeRegistry
from dfsha.v1.records_pb2 import NodeRecord

BLOCK = 16 * 1024 * 1024


def _registry(free: dict[str, int]) -> NodeRegistry:
    registry = NodeRegistry()
    for node_id, free_bytes in free.items():
        registry.register(NodeRecord(node_id=node_id, addr=f"{node_id}:50052"), free_bytes)
    return registry


def test_full_nodes_are_never_chosen() -> None:
    # Un nodo lleno sigue vivo, pero no tiene sitio para el bloque (E2, etapa 10): con 3 nodos y uno lleno,
    # cada bloque va a los otros dos, aunque falte la tercera réplica
    registry = _registry({"datanode-1": 100 * BLOCK, "datanode-2": 100 * BLOCK, "datanode-3": BLOCK - 1})
    for nodes in registry.choose_nodes(20, 3, BLOCK):
        assert sorted(nodes) == ["datanode-1:50052", "datanode-2:50052"]


def test_space_runs_out_during_a_reservation() -> None:
    # Con espacio para 2 bloques por nodo, a partir del tercero no quedan nodos con sitio
    registry = _registry({f"datanode-{n}": 2 * BLOCK for n in (1, 2, 3)})
    placements = registry.choose_nodes(3, 3, BLOCK)
    assert [len(nodes) for nodes in placements] == [3, 3, 0]


def test_dead_nodes_report_time_since_last_heartbeat() -> None:
    now = [100.0]
    registry = NodeRegistry(suspect_after_s=9, dead_after_s=30, clock=lambda: now[0])
    registry.register(NodeRecord(node_id="datanode-1", addr="datanode-1:50052"), BLOCK)
    registry.register(NodeRecord(node_id="datanode-2", addr="datanode-2:50052"), BLOCK)
    now[0] = 125.0
    registry.record_heartbeat("datanode-2", BLOCK)
    assert registry.get_dead_nodes() == {}
    now[0] = 131.0  # datanode-1 lleva 31 s sin latido; datanode-2, 6 s
    assert registry.get_dead_nodes() == {"datanode-1": 31.0}
