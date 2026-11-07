"""Re-replicación, réplicas de más y réplicas corruptas (fase I §8.5 y §9.3).

Una pasada periódica del líder, fuera del modo seguro, compara las réplicas de cada bloque vivo con el
factor de replicación R. Las órdenes no se envían: esperan en una cola por nodo y salen en la respuesta a su
siguiente latido (§9.2). Si una orden se pierde, la pasada siguiente la vuelve a calcular.
"""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from dfsha.common.security import create_block_token
from dfsha.metadata.etcd_client import op_delete
from dfsha.metadata.nodes import NodeState
from dfsha.v1 import common_pb2, metadata_pb2
from dfsha.v1.records_pb2 import ReplicaRecord, VersionRecord

if TYPE_CHECKING:
    from dfsha.metadata.service import MetadataService

logger = logging.getLogger(__name__)

MAX_REPLICATIONS_PER_SOURCE = 4  # copias simultáneas que sirve cada nodo origen
REPLICATION_TIMEOUT_S = 60.0  # una copia sin aviso de bloque recibido en ese tiempo se vuelve a ordenar


@dataclass
class _Replica:
    node_id: str
    record: ReplicaRecord


class ReplicationManager:
    def __init__(self, service: "MetadataService", clock: Callable[[], float] = time.monotonic) -> None:
        self._service = service
        self._clock = clock
        self._lock = threading.Lock()
        self._queues: dict[str, list[metadata_pb2.DataNodeCommand]] = {}
        self._in_flight: dict[str, dict[str, float]] = {}  # block_id -> nodo destino -> plazo
        self._lost: set[str] = set()
        self._dead: set[str] = set()  # nodos que ya se registraron como caídos
        self._under_replicated = 0  # bloques vivos con menos de R réplicas sanas en la pasada anterior

    def reset(self) -> None:
        """Al cambiar de líder, las colas y las copias en curso del anterior no valen."""
        with self._lock:
            self._queues.clear()
            self._in_flight.clear()
            self._dead.clear()

    def queue(self, node_id: str, command: metadata_pb2.DataNodeCommand) -> None:
        with self._lock:
            self._queues.setdefault(node_id, []).append(command)

    def pop_commands(self, node_id: str) -> list[metadata_pb2.DataNodeCommand]:
        with self._lock:
            return self._queues.pop(node_id, [])

    def run_pass(self) -> None:
        """Una pasada sobre todos los bloques vivos, primero los que tienen menos réplicas sanas."""
        service = self._service
        registry = service.registry
        self._log_node_changes()
        now = service._now()
        version_kvs, revision = service.store.etcd.get_prefix(service.keys.all_versions_prefix())
        live: dict[str, metadata_pb2.CommittedBlock] = {}
        for kv in version_kvs:
            version = VersionRecord.FromString(kv.value)
            if not version.HasField("expires_at") or version.expires_at.ToNanoseconds() / 1e9 > now:
                live.update((block.block_id, block) for block in version.blocks)
        prefix = service.keys.all_replicas_prefix()
        replica_kvs, _ = service.store.etcd.get_prefix(prefix, revision=revision)
        replicas: dict[str, list[_Replica]] = {}
        for kv in replica_kvs:
            block_id, _, node_id = kv.key[len(prefix) :].decode().partition("/")
            replicas.setdefault(block_id, []).append(_Replica(node_id, ReplicaRecord.FromString(kv.value)))

        alive = {node_id: (addr, free) for node_id, addr, free in registry.get_alive_nodes()}
        factor = service.settings.replication_factor
        load: dict[str, int] = {}  # copias ordenadas a cada origen en esta pasada
        record_deletes = []
        self._forget_finished(replicas)

        def healthy(block: metadata_pb2.CommittedBlock) -> list[_Replica]:
            return [
                replica
                for replica in replicas.get(block.block_id, [])
                if not replica.record.is_corrupt
                and replica.record.block_sha256 == block.block_sha256
                and registry.get_state(replica.node_id) is not NodeState.DEAD
            ]

        under_replicated = sum(1 for block in live.values() if 0 < len(healthy(block)) < factor)
        if under_replicated and not self._under_replicated:
            logger.warning("%d bloques vivos tienen menos de %d réplicas sanas: empieza la re-replicación", under_replicated, factor)
        elif self._under_replicated and not under_replicated:
            logger.info("Todos los bloques vivos vuelven a tener %d réplicas sanas", factor)  # fin de la re-replicación (E6)
        self._under_replicated = under_replicated
        for block in sorted(live.values(), key=lambda block: len(healthy(block))):
            sane = healthy(block)
            holders = {replica.node_id for replica in replicas.get(block.block_id, [])}
            with self._lock:
                in_flight = dict(self._in_flight.get(block.block_id, {}))
            if not sane:
                if block.block_id not in self._lost:
                    self._lost.add(block.block_id)
                    logger.error("El bloque %s no tiene ninguna réplica sana: está perdido", block.block_id)
                continue
            self._lost.discard(block.block_id)
            missing = factor - len(sane) - len(in_flight)
            if missing > 0:
                self._order_copies(block.block_id, sane, holders | set(in_flight), alive, load, missing)
            elif not in_flight:
                record_deletes.extend(self._order_deletes(block.block_id, sane, replicas.get(block.block_id, []), alive, factor))
        for start in range(0, len(record_deletes), 100):
            service._apply_without_request([], record_deletes[start : start + 100])

    def _log_node_changes(self) -> None:
        """Registra cuándo un nodo pasa a caído y cuándo vuelve: es el tiempo de detección de E6 (§9.2)."""
        dead = self._service.registry.get_dead_nodes()
        for node_id in sorted(dead.keys() - self._dead):
            since = dead[node_id]
            detail = f"último latido hace {since:.1f} s" if since is not None else "sin latido desde la elección"
            logger.warning("Nodo de datos %s declarado caído (%s)", node_id, detail)
        for node_id in sorted(self._dead - dead.keys()):
            logger.info("Nodo de datos %s vuelve a enviar latidos", node_id)
        self._dead = set(dead)

    def _forget_finished(self, replicas: dict[str, list[_Replica]]) -> None:
        """Olvida las copias que ya avisaron de su bloque recibido o que agotaron su plazo."""
        now = self._clock()
        with self._lock:
            for block_id in list(self._in_flight):
                arrived = {replica.node_id for replica in replicas.get(block_id, [])}
                targets = self._in_flight[block_id]
                for node_id in list(targets):
                    if node_id in arrived or targets[node_id] <= now:
                        del targets[node_id]
                if not targets:
                    del self._in_flight[block_id]

    def _order_copies(
        self,
        block_id: str,
        sane: list[_Replica],
        excluded: set[str],
        alive: dict[str, tuple[str, int]],
        load: dict[str, int],
        missing: int,
    ) -> None:
        sources = [replica.node_id for replica in sane if replica.node_id in alive]
        targets = sorted((node_id for node_id in alive if node_id not in excluded), key=lambda node_id: alive[node_id][1], reverse=True)
        for target in targets[:missing]:
            available = [node_id for node_id in sources if load.get(node_id, 0) < MAX_REPLICATIONS_PER_SOURCE]
            if not available:
                return  # los orígenes ya tienen bastante trabajo en esta pasada
            source = min(available, key=lambda node_id: load.get(node_id, 0))
            load[source] = load.get(source, 0) + 1
            token = create_block_token(
                self._service._security.block_token_key, block_id, common_pb2.BLOCK_OPERATION_WRITE, self._service._now()
            )
            self.queue(
                source,
                metadata_pb2.DataNodeCommand(
                    type=metadata_pb2.DATA_NODE_COMMAND_TYPE_REPLICATE, block_id=block_id,
                    target_addr=alive[target][0], target_block_token=token,
                ),
            )  # fmt: skip
            with self._lock:
                self._in_flight.setdefault(block_id, {})[target] = self._clock() + REPLICATION_TIMEOUT_S
            logger.info("Re-replicación del bloque %s: de %s a %s (%d réplicas sanas)", block_id, source, target, len(sane))

    def _order_deletes(
        self,
        block_id: str,
        sane: list[_Replica],
        all_replicas: list[_Replica],
        alive: dict[str, tuple[str, int]],
        factor: int,
    ) -> list:
        """Borra las réplicas de más y, con R sanas, las corruptas. Nunca baja de R réplicas sanas."""
        doomed: list[str] = []
        if len(sane) >= factor:
            sane_ids = {replica.node_id for replica in sane}
            doomed += [replica.node_id for replica in all_replicas if replica.node_id not in sane_ids and replica.node_id in alive]
        extra = [replica.node_id for replica in sane if replica.node_id in alive]
        extra.sort(key=lambda node_id: alive[node_id][1])  # se borra en los que tienen menos espacio libre
        doomed += extra[: max(0, len(sane) - factor)]
        ops = []
        for node_id in doomed:
            self.queue(node_id, metadata_pb2.DataNodeCommand(type=metadata_pb2.DATA_NODE_COMMAND_TYPE_DELETE, block_id=block_id))
            ops.append(op_delete(self._service.keys.replica(block_id, node_id)))
            logger.info("Réplica del bloque %s en %s: de más o corrupta, se ordena borrarla", block_id, node_id)
        return ops
