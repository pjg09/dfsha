"""Relación del nodo de datos con el líder de metadatos: alta, latidos, avisos e informes (§3.4, ADR 0018).

El nodo solo conoce las direcciones de los servidores de metadatos (ADR 0021). Si llama a un seguidor,
recibe NODE_NOT_LEADER con la dirección del líder y repite allí. Recuerda la mayor época del líder que ha
visto y descarta las órdenes que llegan con una menor (cercado, ADR 0039).
"""

import logging
import threading
from collections.abc import Callable, Sequence
from typing import TypeVar

import grpc

from dfsha.common.errors import DfshaError, Reason
from dfsha.datanode.block_store import BlockStore
from dfsha.v1 import metadata_pb2, metadata_pb2_grpc

logger = logging.getLogger(__name__)

T = TypeVar("T")


class MetadataUnavailableError(RuntimeError):
    """No se pudo hablar con el líder de metadatos."""


class MetadataClient:
    def __init__(
        self,
        metadata_addrs: Sequence[str],
        node_id: str,
        addr: str,
        store: BlockStore,
        heartbeat_interval_s: float = 3.0,
        timeout_s: float = 2.0,
        retry_interval_s: float = 1.0,
    ) -> None:
        self._addrs = list(metadata_addrs)
        self._node_id = node_id
        self._addr = addr
        self._hostname = addr.rpartition(":")[0]
        self._store = store
        self._heartbeat_interval_s = heartbeat_interval_s
        self._timeout_s = timeout_s
        self._retry_interval_s = min(retry_interval_s, heartbeat_interval_s)
        self._lock = threading.Lock()
        self._channels: dict[str, grpc.Channel] = {}
        self._leader_addr = self._addrs[0]
        self._max_leader_epoch = 0
        self._is_registered = False
        self._stopped = threading.Event()
        self._thread: threading.Thread | None = None
        self.executed_commands: list[metadata_pb2.DataNodeCommand] = []  # para las pruebas

    @property
    def max_leader_epoch(self) -> int:
        return self._max_leader_epoch

    @property
    def is_registered(self) -> bool:
        return self._is_registered

    # ----- Ciclo de vida -------------------------------------------------------------------------

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="heartbeat", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopped.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        with self._lock:
            for channel in self._channels.values():
                channel.close()
            self._channels.clear()

    def _run(self) -> None:
        while not self._stopped.is_set():
            wait_s = self._heartbeat_interval_s
            try:
                if not self._is_registered:
                    self.register()
                else:
                    self.send_heartbeat()
            except MetadataUnavailableError as error:
                logger.warning("Sin contacto con el líder de metadatos: %s", error)
                wait_s = self._retry_interval_s  # tras una elección, volver cuanto antes a contar como vivo
            self._stopped.wait(wait_s)

    # ----- Mensajes ------------------------------------------------------------------------------

    def register(self) -> None:
        response = self._call(
            lambda stub: stub.RegisterDataNode(
                metadata_pb2.RegisterDataNodeRequest(
                    node_id=self._node_id,
                    hostname=self._hostname,
                    addr=self._addr,
                    capacity_bytes=self._store.get_capacity_bytes(),
                    free_bytes=self._store.get_free_bytes(),
                ),
                timeout=self._timeout_s,
            )
        )
        self._is_registered = True
        logger.info("Dado de alta en el líder de metadatos %s", self._leader_addr)
        if response.is_block_report_required:
            self.send_block_report()

    def send_heartbeat(self) -> None:
        try:
            response = self._call(
                lambda stub: stub.ReportHeartbeat(
                    metadata_pb2.ReportHeartbeatRequest(node_id=self._node_id, free_bytes=self._store.get_free_bytes()),
                    timeout=self._timeout_s,
                )
            )
        except DfshaError as error:
            if error.code is grpc.StatusCode.FAILED_PRECONDITION:
                self._is_registered = False  # el líder no lo conoce: vuelve a darse de alta
                return
            raise
        self.handle_commands(response.leader_epoch, list(response.commands))

    def send_block_report(self) -> None:
        blocks = [
            metadata_pb2.StoredBlock(block_id=meta.block_id, block_sha256=meta.sha256, size_bytes=meta.size_bytes)
            for meta in self._store.list_blocks()
        ]
        response = self._call(
            lambda stub: stub.ReportBlocks(
                metadata_pb2.ReportBlocksRequest(node_id=self._node_id, blocks=blocks), timeout=self._timeout_s
            )
        )
        logger.info("Informe de bloques enviado: %d bloques", len(blocks))
        self.handle_commands(response.leader_epoch, list(response.commands))

    def report_block_received(self, block: metadata_pb2.StoredBlock) -> None:
        """Aviso de bloque recibido (§8.4). Lanza MetadataUnavailableError si no llega al líder."""
        self._call(
            lambda stub: stub.ReportBlockReceived(
                metadata_pb2.ReportBlockReceivedRequest(node_id=self._node_id, block=block), timeout=self._timeout_s
            )
        )

    def handle_commands(self, leader_epoch: int, commands: list[metadata_pb2.DataNodeCommand]) -> None:
        """Ejecuta las órdenes del líder, salvo que vengan de una época anterior a la mayor conocida."""
        with self._lock:
            if leader_epoch < self._max_leader_epoch:
                if commands:
                    logger.warning(
                        "Descartadas %d órdenes de un líder depuesto (época %d < %d)",
                        len(commands), leader_epoch, self._max_leader_epoch,
                    )  # fmt: skip
                return
            self._max_leader_epoch = leader_epoch
        for command in commands:
            self.executed_commands.append(command)
            if command.type == metadata_pb2.DATA_NODE_COMMAND_TYPE_SEND_BLOCK_REPORT:
                self.send_block_report()
            else:
                # REPLICATE, DELETE y VERIFY llegan en la etapa 9 (ADR 0018 y 0032)
                logger.warning("Orden %s todavía no implementada", metadata_pb2.DataNodeCommandType.Name(command.type))

    # ----- Conexión con el líder -----------------------------------------------------------------

    def _call(self, operation: Callable[[metadata_pb2_grpc.MetadataServiceStub], T]) -> T:
        """Llama al líder; sigue las redirecciones NODE_NOT_LEADER y prueba los demás servidores."""
        candidates = [self._leader_addr, *[addr for addr in self._addrs if addr != self._leader_addr]]
        tried: set[str] = set()
        while candidates:
            addr = candidates.pop(0)
            if addr in tried:
                continue
            tried.add(addr)
            try:
                result = operation(metadata_pb2_grpc.MetadataServiceStub(self._get_channel(addr)))
                self._leader_addr = addr
                return result
            except grpc.RpcError as rpc_error:
                error = DfshaError.from_rpc_error(rpc_error)
                if error.reason is Reason.NODE_NOT_LEADER:
                    leader_addr = error.metadata.get("leader_addr", "")
                    if leader_addr and leader_addr not in tried:
                        candidates.insert(0, leader_addr)
                    continue
                if error.code in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
                    continue
                raise error from rpc_error
        raise MetadataUnavailableError(f"Ningún servidor de metadatos atiende como líder ({', '.join(self._addrs)})")

    def _get_channel(self, addr: str) -> grpc.Channel:
        with self._lock:
            channel = self._channels.get(addr)
            if channel is None:
                channel = self._channels[addr] = grpc.insecure_channel(addr)
            return channel

