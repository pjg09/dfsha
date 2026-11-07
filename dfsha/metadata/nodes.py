"""Registro de nodos de datos en la memoria del líder y ubicación de réplicas (fase I §4.3 y §9.2).

El estado de vida de cada nodo depende de su último latido y solo vive en la memoria del líder: no
está en etcd (ADR 0018 y 0031). Tras cada elección, ningún nodo cuenta como vivo hasta que envía un
latido al nuevo líder.
"""

import enum
import random
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from dfsha.v1.records_pb2 import NodeRecord


class NodeState(enum.Enum):
    WITHOUT_HEARTBEAT = "sin latido desde la elección"
    ALIVE = "vivo"
    SUSPECT = "sospechoso"
    DEAD = "caído"


@dataclass
class _Node:
    record: NodeRecord
    free_bytes: int = 0
    last_heartbeat: float | None = None  # reloj monótono


class NodeRegistry:
    def __init__(
        self,
        suspect_after_s: float = 9.0,
        dead_after_s: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._suspect_after_s = suspect_after_s
        self._dead_after_s = dead_after_s
        self._clock = clock
        self._lock = threading.Lock()
        self._nodes: dict[str, _Node] = {}
        self._elected_at = clock()

    def reset_for_election(self, records: Iterable[NodeRecord]) -> None:
        """Al ser elegido: conoce los nodos registrados en etcd, pero ninguno tiene latido todavía."""
        with self._lock:
            self._nodes = {record.node_id: _Node(record) for record in records}
            self._elected_at = self._clock()

    def register(self, record: NodeRecord, free_bytes: int) -> None:
        with self._lock:
            self._nodes[record.node_id] = _Node(record, free_bytes, self._clock())

    def record_heartbeat(self, node_id: str, free_bytes: int) -> bool:
        """Anota un latido. Devuelve False si el nodo no está registrado."""
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return False
            node.free_bytes = free_bytes
            node.last_heartbeat = self._clock()
            return True

    def get_state(self, node_id: str) -> NodeState:
        with self._lock:
            node = self._nodes.get(node_id)
            return self._get_state(node) if node is not None else NodeState.DEAD

    def get_dead_nodes(self) -> dict[str, float | None]:
        """Nodos caídos y los segundos desde su último latido (None si no envió ninguno desde la elección)."""
        with self._lock:
            now = self._clock()
            return {
                node_id: (now - node.last_heartbeat if node.last_heartbeat is not None else None)
                for node_id, node in self._nodes.items()
                if self._get_state(node) is NodeState.DEAD
            }

    def get_alive_nodes(self) -> list[tuple[str, str, int]]:
        """(node_id, dirección, espacio libre) de los nodos vivos."""
        with self._lock:
            return [
                (node.record.node_id, node.record.addr, node.free_bytes)
                for node in self._nodes.values()
                if self._get_state(node) is NodeState.ALIVE
            ]

    def find_node_id(self, node_id_or_addr: str) -> str | None:
        """El node_id de un nodo dado por su node_id o por su dirección (el cliente solo conoce direcciones)."""
        with self._lock:
            if node_id_or_addr in self._nodes:
                return node_id_or_addr
            return next((node_id for node_id, node in self._nodes.items() if node.record.addr == node_id_or_addr), None)

    def get_addr(self, node_id: str) -> str | None:
        with self._lock:
            node = self._nodes.get(node_id)
            return node.record.addr if node is not None else None

    def choose_nodes(
        self, block_count: int, replication_factor: int, block_size_bytes: int, excluded_addrs: Iterable[str] = ()
    ) -> list[list[str]]:
        """Elige los nodos de cada bloque, con la primaria primero (fase I §4.3).

        Solo nodos vivos y con sitio para el bloque; los de más espacio libre, con desempate aleatorio; nunca
        dos réplicas de un bloque en el mismo nodo. Cada bloque asignado descuenta su tamaño del espacio libre previsto de
        sus nodos, para que los bloques de una misma reserva se repartan entre todos los nodos. Los nodos de
        ``excluded_addrs`` ya fallaron con esos bloques y no se eligen (ADR 0044).
        """
        excluded = set(excluded_addrs)
        with self._lock:
            candidates = [
                node
                for node in self._nodes.values()
                if self._get_state(node) is NodeState.ALIVE and node.record.addr not in excluded
            ]
            projected_free = {node.record.node_id: node.free_bytes for node in candidates}
            addrs = {node.record.node_id: node.record.addr for node in candidates}
        placements: list[list[str]] = []
        for block_position in range(block_count):
            # Un nodo sin sitio para el bloque no se elige, aunque esté vivo (se llenaba en E2, etapa 10)
            order = [node_id for node_id, free in projected_free.items() if free >= block_size_bytes]
            random.shuffle(order)  # desempate aleatorio
            order.sort(key=lambda node_id: projected_free[node_id], reverse=True)
            chosen = order[:replication_factor]
            for node_id in chosen:
                projected_free[node_id] -= block_size_bytes
            rotation = block_position % len(chosen) if chosen else 0
            chosen = chosen[rotation:] + chosen[:rotation]  # la primaria rota entre bloques consecutivos
            placements.append([addrs[node_id] for node_id in chosen])
        return placements

    def _get_state(self, node: _Node) -> NodeState:
        now = self._clock()
        if node.last_heartbeat is None or node.last_heartbeat < self._elected_at:
            if now - self._elected_at >= self._dead_after_s:
                return NodeState.DEAD
            return NodeState.WITHOUT_HEARTBEAT
        age_s = now - node.last_heartbeat
        if age_s < self._suspect_after_s:
            return NodeState.ALIVE
        if age_s < self._dead_after_s:
            return NodeState.SUSPECT
        return NodeState.DEAD
