"""Servicio DataNodeService: escritura y lectura de bloques en flujo (fase I §4.4, §6.1, §6.2 y §8.4)."""

import hashlib
import logging
import os
import queue
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Protocol

import grpc

from dfsha.common.errors import DfshaError, Reason
from dfsha.datanode.block_store import BlockMeta, BlockStore, StagingBlock
from dfsha.common.security import check_block_token
from dfsha.common.tls import get_peer_role
from dfsha.v1 import common_pb2, datanode_pb2, datanode_pb2_grpc, metadata_pb2

logger = logging.getLogger(__name__)

CHUNK_SIZE_BYTES = 1024 * 1024  # mensajes de 1 MiB (fase I §5.2)
# Margen sobre el tamaño de bloque para el nonce y la etiqueta de AES-GCM (fase I §10.5)
ENCRYPTION_OVERHEAD_MAX_BYTES = 1024


class BlockReporter(Protocol):
    """Avisa al servidor de metadatos de cada bloque guardado (ReportBlockReceived, §8.4)."""

    def report_block_received(self, block: metadata_pb2.StoredBlock) -> None: ...

    def report_corrupt_replica(self, block_id: str) -> None: ...


class LoggingBlockReporter:
    """Solo deja constancia en el log. Lo sustituye el aviso real cuando exista el servidor de metadatos."""

    def report_block_received(self, block: metadata_pb2.StoredBlock) -> None:
        logger.info("Bloque %s guardado y verificado (%d bytes)", block.block_id, block.size_bytes)

    def report_corrupt_replica(self, block_id: str) -> None:
        logger.error("Réplica corrupta del bloque %s", block_id)


@dataclass(frozen=True)
class DataNodeSettings:
    node_id: str
    addr: str  # dirección por la que lo conocen los demás, host:puerto
    block_size_bytes: int = 16 * 1024 * 1024
    write_quorum: int = 2
    transfer_timeout_s: float = 60.0


class ChannelPool:
    """Un canal gRPC por dirección, reutilizado entre llamadas."""

    def __init__(self, create_channel: Callable[[str], grpc.Channel] = grpc.insecure_channel) -> None:
        self._create_channel = create_channel
        self._channels: dict[str, grpc.Channel] = {}
        self._lock = threading.Lock()

    def get_stub(self, addr: str) -> datanode_pb2_grpc.DataNodeServiceStub:
        with self._lock:
            channel = self._channels.get(addr)
            if channel is None:
                channel = self._channels[addr] = self._create_channel(addr)
        return datanode_pb2_grpc.DataNodeServiceStub(channel)

    def close(self) -> None:
        with self._lock:
            for channel in self._channels.values():
                channel.close()
            self._channels.clear()


class _Forward:
    """Reenvío de un bloque de la primaria a una secundaria, leyendo del área temporal."""

    def __init__(
        self,
        addr: str,
        header: datanode_pb2.WriteBlockHeader,
        staging: StagingBlock,
        stub: datanode_pb2_grpc.DataNodeServiceStub,
        timeout_s: float,
    ) -> None:
        self.addr = addr
        self._header = header
        self._staging = staging
        self._timeout_s = timeout_s
        # El descriptor se abre antes del renombrado: sigue valiendo cuando el bloque pasa al almacén
        self._descriptor = os.open(staging.path, os.O_RDONLY)
        self.future: grpc.Future = stub.WriteBlock.future(self._requests(), timeout=timeout_s)

    def _requests(self) -> Iterator[datanode_pb2.WriteBlockRequest]:
        try:
            yield datanode_pb2.WriteBlockRequest(header=self._header)
            offset = 0
            while True:
                available = self._staging.wait_for_data(offset, self._timeout_s)
                if available is None:
                    return  # la escritura falló: la secundaria recibe un bloque incompleto y lo descarta
                if available == 0:
                    return  # bloque completo enviado
                while offset < available:
                    size = min(CHUNK_SIZE_BYTES, available - offset)
                    data = os.pread(self._descriptor, size, offset)
                    offset += len(data)
                    yield datanode_pb2.WriteBlockRequest(data=data)
        finally:
            os.close(self._descriptor)

    def cancel(self) -> None:
        self.future.cancel()


class DataNodeService(datanode_pb2_grpc.DataNodeServiceServicer):
    def __init__(
        self,
        settings: DataNodeSettings,
        store: BlockStore,
        reporter: BlockReporter,
        channels: ChannelPool,
        block_token_key: bytes,
    ) -> None:
        self._settings = settings
        self._store = store
        self._reporter = reporter
        self._channels = channels
        self._block_token_key = block_token_key

    def WriteBlock(  # noqa: N802 (nombre del RPC)
        self, request_iterator: Iterator[datanode_pb2.WriteBlockRequest], context: grpc.ServicerContext
    ) -> datanode_pb2.WriteBlockResponse:
        try:
            self._require_peer(context)
            return self._write_block(request_iterator)
        except DfshaError as error:
            context.abort_with_status(error.to_status())

    def ReadBlock(  # noqa: N802 (nombre del RPC)
        self, request: datanode_pb2.ReadBlockRequest, context: grpc.ServicerContext
    ) -> Iterator[datanode_pb2.ReadBlockResponse]:
        try:
            self._require_peer(context)
            yield from self._read_block(request)
        except DfshaError as error:
            context.abort_with_status(error.to_status())

    # ----- Órdenes del líder (§8.5 y §9.3) -------------------------------------------------------

    def replicate_block(self, block_id: str, target_addr: str, token: common_pb2.BlockToken) -> None:
        """Orden REPLICATE: copia la réplica a otro nodo con WriteBlock y el token de escritura del líder."""
        block_path, meta = self._store.get_block(block_id)

        def requests() -> Iterator[datanode_pb2.WriteBlockRequest]:
            header = datanode_pb2.WriteBlockHeader(
                block_id=block_id, block_token=token, block_sha256=meta.sha256, size_bytes=meta.size_bytes
            )
            yield datanode_pb2.WriteBlockRequest(header=header)
            with open(block_path, "rb") as block_file:
                while data := block_file.read(CHUNK_SIZE_BYTES):
                    yield datanode_pb2.WriteBlockRequest(data=data)

        self._channels.get_stub(target_addr).WriteBlock(requests(), timeout=self._settings.transfer_timeout_s)
        logger.info("Bloque %s copiado a %s (re-replicación)", block_id, target_addr)

    def verify_block(self, block_id: str, rate_bytes_s: float = 0) -> bool:
        """Orden VERIFY y verificador periódico: recalcula el hash y avisa si no coincide."""
        block_path, meta = self._store.get_block(block_id)
        hasher = hashlib.sha256()
        started = time.monotonic()
        read_bytes = 0
        with open(block_path, "rb") as block_file:
            while data := block_file.read(CHUNK_SIZE_BYTES):
                hasher.update(data)
                read_bytes += len(data)
                if rate_bytes_s:
                    time.sleep(max(0.0, read_bytes / rate_bytes_s - (time.monotonic() - started)))
        if hasher.digest() == meta.sha256:
            return True
        logger.error("El bloque %s no coincide con su hash en disco (verificación)", block_id)
        self._report_corrupt(block_id)
        return False

    def _report_corrupt(self, block_id: str) -> None:
        try:
            self._reporter.report_corrupt_replica(block_id)
        except Exception as error:  # noqa: BLE001 - la verificación periódica lo volverá a encontrar
            logger.warning("No se pudo avisar de la réplica corrupta %s: %s", block_id, error)

    @staticmethod
    def _require_peer(context: grpc.ServicerContext) -> None:
        """Solo clientes y nodos de datos (reenvío y re-replicación) llaman a un nodo de datos (§10.3)."""
        if get_peer_role(context) not in ("client", "datanode"):
            raise DfshaError(grpc.StatusCode.PERMISSION_DENIED, "Este certificado no puede llamar a un nodo de datos")

    def _verify_block_token(self, token: common_pb2.BlockToken, block_id: str, operation: common_pb2.BlockOperation) -> None:
        """Firma, bloque, operación y caducidad, sin consultar a nadie (§10.3)."""
        problem = check_block_token(self._block_token_key, token, block_id, operation)
        if problem is not None:
            raise DfshaError(
                grpc.StatusCode.PERMISSION_DENIED, f"Token de bloque no válido: {problem.message}", Reason.BLOCK_TOKEN_INVALID
            )

    def _write_block(self, request_iterator: Iterator[datanode_pb2.WriteBlockRequest]) -> datanode_pb2.WriteBlockResponse:
        header = self._read_header(request_iterator)
        staging = self._store.create_staging(header.block_id, header.block_sha256, header.size_bytes)
        forwards = [self._start_forward(addr, header, staging) for addr in header.secondary_addrs]
        try:
            for request in request_iterator:
                if request.WhichOneof("content") != "data":
                    raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "La cabecera solo puede ir en el primer mensaje")
                staging.append(request.data)
            meta = staging.finish()
        except BaseException:
            # Bloque corrupto, cliente que se va o error de disco: nada de esto cuenta como réplica
            for forward in forwards:
                forward.cancel()
            self._store.discard(staging)
            raise
        if self._store.commit(staging, meta):
            logger.info("Bloque %s guardado (%d bytes)", meta.block_id, meta.size_bytes)
        try:
            # Antes de responder: así, cuando el cliente recibe OK, W nodos ya han avisado (§8.4)
            self._reporter.report_block_received(
                metadata_pb2.StoredBlock(block_id=meta.block_id, block_sha256=meta.sha256, size_bytes=meta.size_bytes)
            )
        except Exception as error:
            # El bloque queda guardado; el informe de bloques lo reconciliará, pero esta réplica no cuenta
            raise DfshaError(
                grpc.StatusCode.UNAVAILABLE,
                f"El bloque {meta.block_id} se guardó, pero no se pudo avisar al servidor de metadatos",
            ) from error
        if not forwards:
            return datanode_pb2.WriteBlockResponse(stored_on=[self._settings.addr])
        return self._wait_for_quorum(meta, forwards)

    def _read_header(self, request_iterator: Iterator[datanode_pb2.WriteBlockRequest]) -> datanode_pb2.WriteBlockHeader:
        first = next(request_iterator, None)
        if first is None or first.WhichOneof("content") != "header":
            raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "El primer mensaje de WriteBlock tiene que ser la cabecera")
        header = first.header
        self._verify_block_token(header.block_token, header.block_id, common_pb2.BLOCK_OPERATION_WRITE)
        if len(header.block_sha256) != 32:
            raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "block_sha256 tiene que tener 32 bytes")
        max_size_bytes = self._settings.block_size_bytes + ENCRYPTION_OVERHEAD_MAX_BYTES
        if header.size_bytes > max_size_bytes:
            raise DfshaError(
                grpc.StatusCode.INVALID_ARGUMENT,
                f"El bloque anuncia {header.size_bytes} bytes; el máximo es {max_size_bytes}",
            )
        if self._settings.addr in header.secondary_addrs:
            raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "La primaria no puede ser también secundaria")
        return header

    def _start_forward(self, addr: str, header: datanode_pb2.WriteBlockHeader, staging: StagingBlock) -> _Forward:
        secondary_header = datanode_pb2.WriteBlockHeader()
        secondary_header.CopyFrom(header)
        del secondary_header.secondary_addrs[:]  # las secundarias no reenvían
        stub = self._channels.get_stub(addr)
        return _Forward(addr, secondary_header, staging, stub, self._settings.transfer_timeout_s)

    def _wait_for_quorum(self, meta: BlockMeta, forwards: list[_Forward]) -> datanode_pb2.WriteBlockResponse:
        """Responde en cuanto W réplicas, la primaria incluida, tienen el bloque (fase I §4.4)."""
        stored_on = [self._settings.addr]
        done: queue.Queue[_Forward] = queue.Queue()
        for forward in forwards:
            forward.future.add_done_callback(lambda _future, forward=forward: done.put(forward))
        for _ in forwards:
            forward = done.get()
            try:
                forward.future.result()
                stored_on.append(forward.addr)
            except (grpc.RpcError, grpc.FutureCancelledError) as error:
                logger.warning("La secundaria %s no guardó el bloque %s: %s", forward.addr, meta.block_id, error)
            if len(stored_on) >= self._settings.write_quorum:
                # La réplica que falta termina en segundo plano; si falla, la re-replicación lo corrige (§9.3)
                return datanode_pb2.WriteBlockResponse(stored_on=stored_on)
        if len(stored_on) >= self._settings.write_quorum:
            return datanode_pb2.WriteBlockResponse(stored_on=stored_on)
        raise DfshaError(
            grpc.StatusCode.UNAVAILABLE,
            f"El bloque {meta.block_id} solo está en {len(stored_on)} réplicas; hacen falta {self._settings.write_quorum}",
            Reason.QUORUM_NOT_REACHED,
        )

    def _read_block(self, request: datanode_pb2.ReadBlockRequest) -> Iterator[datanode_pb2.ReadBlockResponse]:
        self._verify_block_token(request.block_token, request.block_id, common_pb2.BLOCK_OPERATION_READ)
        block_path, meta = self._store.get_block(request.block_id)
        yield datanode_pb2.ReadBlockResponse(
            header=datanode_pb2.ReadBlockHeader(size_bytes=meta.size_bytes, block_sha256=meta.sha256)
        )
        hasher = hashlib.sha256()
        with open(block_path, "rb") as block_file:
            while data := block_file.read(CHUNK_SIZE_BYTES):
                hasher.update(data)
                yield datanode_pb2.ReadBlockResponse(data=data)
        if hasher.digest() != meta.sha256:
            # Réplica corrupta en disco: el cliente descarta lo recibido y lee de otra (§8.3, §8.5)
            logger.error("El bloque %s no coincide con su hash en disco", meta.block_id)
            self._report_corrupt(meta.block_id)
            raise DfshaError(
                grpc.StatusCode.DATA_LOSS, f"La réplica del bloque {meta.block_id} está corrupta", Reason.BLOCK_CORRUPTED
            )
