"""Biblioteca de cliente: operaciones de RF1 y RF2 sobre los RPC de metadatos y de datos (§3.5, §6)."""

import hashlib
import logging
import os
import random
import threading
import time
import uuid
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import grpc

from dfsha.client.file_handle import FileHandle
from dfsha.client.connection import ChannelPool, MetadataConnection, RetryPolicy, get_datanode_stub
from dfsha.common import config
from dfsha.common.errors import DfshaError, Reason
from dfsha.common.security import decrypt_block, encrypt_block
from dfsha.common.tls import DEFAULT_SECRETS_DIRECTORY, load_identity, make_channel_factory
from dfsha.v1 import common_pb2, datanode_pb2, metadata_pb2

logger = logging.getLogger(__name__)

CHUNK_SIZE_BYTES = 1024 * 1024  # mensajes de 1 MiB (§5.2)
WHOLE_FILE = common_pb2.BlockRange(first_block_index=0, block_count=0)
MAX_BLOCKS_PER_ALLOCATION = 1024
MAX_BLOCK_ATTEMPTS = 4


@dataclass(frozen=True)
class ClientSettings:
    metadata_addrs: list[str]
    secrets_directory: Path  # ca.pem, cert.pem y key.pem del host cliente (TLS mutuo, ADR 0043)
    username: str
    password: str
    rpc_timeout_s: float = 10.0
    transfer_timeout_s: float = 120.0
    transfer_inactivity_s: float = 10.0  # sin ningún mensaje en este tiempo, se corta la transferencia (E6)
    parallel_transfers: int = 4
    retry: RetryPolicy = field(default_factory=RetryPolicy)


def load_settings(password: str | None = None) -> ClientSettings:
    """Lee la configuración de las variables DFSHA_* (convenciones §2).

    La contraseña sale de DFSHA_PASSWORD o, si no está, del argumento (la pide la línea de órdenes).
    """
    return ClientSettings(
        metadata_addrs=config.get_addrs("METADATA_ADDRS"),
        secrets_directory=Path(config.get_str("SECRETS_DIRECTORY", DEFAULT_SECRETS_DIRECTORY)),
        username=config.get_str("USERNAME"),
        password=config.get_str("PASSWORD", password),
        rpc_timeout_s=config.get_float("RPC_TIMEOUT_S", 10.0),
        transfer_timeout_s=config.get_float("TRANSFER_TIMEOUT_S", 120.0),
        transfer_inactivity_s=config.get_float("TRANSFER_INACTIVITY_S", 10.0),
        parallel_transfers=config.get_int("PARALLEL_TRANSFERS", 4),
        retry=RetryPolicy(max_attempts=config.get_int("MAX_ATTEMPTS", 8)),
    )


def _request_id() -> str:
    return str(uuid.uuid4())


def _get_failed_addrs(error: DfshaError, primary: str) -> list[str]:
    """Nodos que fallaron al escribir un bloque, para no volver a pedirlos (ADR 0044).

    Sin motivo de DFSha, no se llegó a hablar con la primaria. Con QUORUM_NOT_REACHED, la primaria sí respondió
    y dice qué secundarias fallaron. En cualquier otro caso no se sabe de nadie que haya fallado.
    """
    if error.reason is None and error.code in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
        return [primary]
    if error.reason is Reason.QUORUM_NOT_REACHED:
        return [addr for addr in error.metadata.get("failed_addrs", "").split(",") if addr]
    return []


class _InactivityWatchdog:
    """Llama a ``on_timeout`` si pasan ``timeout_s`` sin un ``reset()``."""

    def __init__(self, on_timeout: Callable[[], object], timeout_s: float) -> None:
        self._on_timeout = on_timeout
        self._timeout_s = timeout_s
        self._last = time.monotonic()
        self._stopped = threading.Event()
        threading.Thread(target=self._run, name="inactivity-watchdog", daemon=True).start()

    def reset(self) -> None:
        self._last = time.monotonic()

    def stop(self) -> None:
        self._stopped.set()

    def _run(self) -> None:
        while not self._stopped.wait(min(0.5, self._timeout_s / 4)):
            if time.monotonic() - self._last > self._timeout_s:
                logger.warning("Sin progreso en %.0f s: se cancela la transferencia", self._timeout_s)
                self._on_timeout()
                return


class _LeaseKeeper:
    """Renueva el arrendamiento mientras dura una escritura larga (§6.1, paso 6)."""

    def __init__(self, client: "DfshaClient", lease_id: str, renew_every_s: float) -> None:
        self._client = client
        self._lease_id = lease_id
        self._renew_every_s = renew_every_s
        self._stopped = threading.Event()
        self.error: DfshaError | None = None
        self._thread = threading.Thread(target=self._run, name="lease-keeper", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stopped.wait(self._renew_every_s):
            request = metadata_pb2.UpdateLeaseRequest(request_id=_request_id(), lease_id=self._lease_id)
            try:
                self._client.metadata.call_rpc("UpdateLease", request)
            except DfshaError as error:
                self.error = error  # la confirmación fallará con LEASE_EXPIRED si de verdad caducó
                return

    def stop(self) -> None:
        self._stopped.set()
        self._thread.join(timeout=5)


class DfshaClient:
    def __init__(self, settings: ClientSettings) -> None:
        self.settings = settings
        self._channels = ChannelPool(make_channel_factory(load_identity(settings.secrets_directory)))
        self.metadata = MetadataConnection(
            settings.metadata_addrs, self._channels, settings.rpc_timeout_s, settings.retry, settings.username, settings.password
        )

    def close(self) -> None:
        self._channels.close()

    def __enter__(self) -> "DfshaClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ===== Usuarios ============================================================================

    def create_user(self, username: str, password: str, is_admin: bool = False) -> str:
        """Da de alta un usuario; solo puede hacerlo un administrador (§10.2)."""
        request = metadata_pb2.CreateUserRequest(request_id=_request_id(), username=username, password=password, is_admin=is_admin)
        return self.metadata.call_rpc("CreateUser", request).user_id

    # ===== RF1: espacio de nombres =============================================================

    def list_directory(self, path: str) -> list[metadata_pb2.DirectoryEntry]:
        request = metadata_pb2.ListDirectoryRequest(path=path)
        return list(self.metadata.call_rpc("ListDirectory", request).entries)

    def get_file_info(self, path: str) -> metadata_pb2.FileInfo:
        request = metadata_pb2.GetFileInfoRequest(path=path)
        return self.metadata.call_rpc("GetFileInfo", request).info

    def create_directory(self, path: str) -> None:
        request = metadata_pb2.CreateDirectoryRequest(request_id=_request_id(), path=path)
        self.metadata.call_rpc("CreateDirectory", request)

    def delete_directory(self, path: str) -> None:
        request = metadata_pb2.DeleteDirectoryRequest(request_id=_request_id(), path=path)
        self.metadata.call_rpc("DeleteDirectory", request)

    def delete_file(self, path: str) -> None:
        request = metadata_pb2.DeleteFileRequest(request_id=_request_id(), path=path)
        self.metadata.call_rpc("DeleteFile", request)

    def move(self, source_path: str, target_path: str) -> None:
        request = metadata_pb2.MovePathRequest(request_id=_request_id(), source_path=source_path, target_path=target_path)
        self.metadata.call_rpc("MovePath", request)

    # ===== RF3: acceso a archivos ==============================================================

    def open(self, path: str, mode: metadata_pb2.OpenMode = metadata_pb2.OPEN_MODE_READ) -> FileHandle:
        """Abre un archivo para leer, para escribir (si existe) o para crearlo al cerrar (§7)."""
        return FileHandle(self, path, mode)

    # ===== RF2: carga y recuperación ===========================================================

    def put(self, local_path: Path, remote_path: str) -> int:
        """Carga un archivo completo: creación si no existe, reemplazo si existe (§6.1). Devuelve la versión."""
        size_bytes = local_path.stat().st_size
        opened, write_mode = self._open_for_put(remote_path)
        block_size = opened.info.block_size_bytes
        block_count = -(-size_bytes // block_size) if size_bytes else 0
        lock_request = metadata_pb2.LockBlocksRequest(request_id=_request_id(), file_handle=opened.file_handle, block_range=WHOLE_FILE)
        lease = self.metadata.call_rpc("LockBlocks", lock_request)
        ttl_s = max(1.0, lease.expires_at.ToNanoseconds() / 1e9 - time.time())
        keeper = _LeaseKeeper(self, lease.lease_id, renew_every_s=ttl_s / 3)
        committed: list[metadata_pb2.CommittedBlock] = []
        try:
            with open(local_path, "rb") as source:
                descriptor = source.fileno()

                def read_block(index: int) -> bytes:
                    offset = index * block_size
                    return os.pread(descriptor, min(block_size, size_bytes - offset), offset)

                committed = self._upload_blocks(
                    opened.file_handle, opened.data_key, lease.lease_id, list(range(block_count)), read_block
                )
            commit_request = metadata_pb2.CommitFileRequest(
                request_id=_request_id(),
                file_handle=opened.file_handle,
                lease_id=lease.lease_id,
                write_mode=write_mode,
                blocks=committed,
                size_bytes=size_bytes,
            )
            return self.metadata.call_rpc("CommitFile", commit_request).version
        except BaseException:
            self._abort(opened.file_handle, lease.lease_id)
            raise
        finally:
            keeper.stop()
            self._unlock(lease.lease_id)

    def get(self, remote_path: str, local_path: Path) -> int:
        """Recupera la versión confirmada completa de un archivo (§6.2). Devuelve su tamaño."""
        open_request = metadata_pb2.OpenFileRequest(path=remote_path, mode=metadata_pb2.OPEN_MODE_READ)
        opened = self.metadata.call_rpc("OpenFile", open_request)
        locate_request = metadata_pb2.GetBlockLocationsRequest(file_handle=opened.file_handle, block_range=WHOLE_FILE)
        locations = self.metadata.call_rpc("GetBlockLocations", locate_request).locations
        block_size = opened.info.block_size_bytes
        failed_addrs: set[str] = set()  # réplicas que ya fallaron en este get: se prueban las últimas
        partial_path = local_path.with_name(local_path.name + ".dfsha-parcial")
        with open(partial_path, "wb") as target:
            descriptor = target.fileno()

            def fetch(location: common_pb2.BlockLocation) -> None:
                stored = self._download_block(location, opened.file_handle, failed_addrs)
                plaintext = decrypt_block(opened.data_key, location.block_id, stored)  # verifica la etiqueta GCM
                os.pwrite(descriptor, plaintext, location.block_index * block_size)

            with ThreadPoolExecutor(self.settings.parallel_transfers) as pool:
                list(pool.map(fetch, locations))
            target.truncate(opened.info.size_bytes)
            os.fsync(descriptor)
        os.replace(partial_path, local_path)  # el archivo local solo aparece entero
        return opened.info.size_bytes

    # ===== Ayudas de put =======================================================================

    def _open_for_put(self, remote_path: str) -> tuple[metadata_pb2.OpenFileResponse, common_pb2.WriteMode]:
        """Abre para crear o, si ya existe, para reemplazar."""
        for _ in range(3):  # otro cliente puede crear o borrar el archivo entre medias
            for mode, write_mode in (
                (metadata_pb2.OPEN_MODE_CREATE, common_pb2.WRITE_MODE_CREATE),
                (metadata_pb2.OPEN_MODE_WRITE, common_pb2.WRITE_MODE_REPLACE),
            ):
                request = metadata_pb2.OpenFileRequest(path=remote_path, mode=mode)
                try:
                    return self.metadata.call_rpc("OpenFile", request), write_mode
                except DfshaError as error:
                    if error.reason not in (Reason.PATH_ALREADY_EXISTS, Reason.PATH_NOT_FOUND) or (
                        error.reason is Reason.PATH_NOT_FOUND and mode == metadata_pb2.OPEN_MODE_CREATE
                    ):
                        raise
        raise DfshaError(grpc.StatusCode.ABORTED, f"{remote_path} cambia demasiado deprisa; vuelve a intentarlo")

    def _allocate(
        self, file_handle: bytes, lease_id: str, indices: list[int], excluded_addrs: Iterable[str] = ()
    ) -> list[common_pb2.BlockLocation]:
        locations: list[common_pb2.BlockLocation] = []
        for start in range(0, len(indices), MAX_BLOCKS_PER_ALLOCATION):
            request = metadata_pb2.AllocateBlocksRequest(
                request_id=_request_id(), file_handle=file_handle, lease_id=lease_id,
                block_indices=indices[start : start + MAX_BLOCKS_PER_ALLOCATION], excluded_datanode_addrs=excluded_addrs,
            )  # fmt: skip
            locations.extend(self.metadata.call_rpc("AllocateBlocks", request).blocks)
        return locations

    def _upload_blocks(
        self,
        file_handle: bytes,
        data_key: bytes,
        lease_id: str,
        indices: list[int],
        read_block: Callable[[int], bytes],
    ) -> list[metadata_pb2.CommittedBlock]:
        """Reserva, cifra y envía los bloques de ``indices``; ``read_block`` da el contenido en claro de cada uno."""
        if not indices:
            return []
        locations = self._allocate(file_handle, lease_id, indices)

        def upload(location: common_pb2.BlockLocation) -> metadata_pb2.CommittedBlock:
            plaintext = read_block(location.block_index)
            failed_addrs: set[str] = set()
            for attempt in range(MAX_BLOCK_ATTEMPTS):
                # Cifrado de sobre (§10.5): el block_id es el dato asociado, así que se cifra de nuevo si cambia
                stored = encrypt_block(data_key, location.block_id, plaintext)
                sha256 = hashlib.sha256(stored).digest()  # el hash es del bloque cifrado, el que guardan los nodos
                try:
                    self._write_block(location, stored, sha256)
                    return metadata_pb2.CommittedBlock(
                        block_index=location.block_index, block_id=location.block_id, block_sha256=sha256, size_bytes=len(stored)
                    )
                except DfshaError as error:
                    if attempt == MAX_BLOCK_ATTEMPTS - 1:
                        raise
                    # Se repite el bloque en otros nodos, con un block_id nuevo (§11.3). El líder puede seguir
                    # contando como vivo un nodo que acaba de caer (§9.2): se le pide que no elija los que fallaron
                    failed_addrs.update(_get_failed_addrs(error, location.datanode_addrs[0]))
                    logger.warning("El bloque %d falló en %s (%s); se reserva de nuevo", location.block_index, location.datanode_addrs[0], error.message)
                    time.sleep(self.settings.retry.get_backoff_s(attempt))
                    location = self._allocate(file_handle, lease_id, [location.block_index], failed_addrs)[0]
            raise AssertionError("inalcanzable")

        with ThreadPoolExecutor(self.settings.parallel_transfers) as pool:
            return list(pool.map(upload, locations))

    def _write_block(self, location: common_pb2.BlockLocation, data: bytes, sha256: bytes) -> None:
        primary, *secondaries = location.datanode_addrs

        watchdog: _InactivityWatchdog | None = None

        def requests() -> Iterator[datanode_pb2.WriteBlockRequest]:
            header = datanode_pb2.WriteBlockHeader(
                block_id=location.block_id, block_token=location.block_token, block_sha256=sha256,
                size_bytes=len(data), secondary_addrs=secondaries,
            )  # fmt: skip
            yield datanode_pb2.WriteBlockRequest(header=header)
            for offset in range(0, len(data), CHUNK_SIZE_BYTES):
                if watchdog is not None:
                    watchdog.reset()  # gRPC pide el trozo siguiente: la primaria está recibiendo
                yield datanode_pb2.WriteBlockRequest(data=data[offset : offset + CHUNK_SIZE_BYTES])

        # Una primaria congelada acepta la conexión y no lee: sin progreso en transfer_inactivity_s se cancela,
        # en lugar de esperar el plazo completo, y el bloque se reserva en otros nodos (E6, etapa 10)
        future = get_datanode_stub(self._channels, primary).WriteBlock.future(requests(), timeout=self.settings.transfer_timeout_s)
        watchdog = _InactivityWatchdog(future.cancel, self.settings.transfer_inactivity_s)
        try:
            future.result()
        except grpc.FutureCancelledError:
            raise DfshaError(grpc.StatusCode.UNAVAILABLE, f"La primaria {primary} no avanzó en {self.settings.transfer_inactivity_s:.0f} s") from None
        except grpc.RpcError as rpc_error:
            raise DfshaError.from_rpc_error(rpc_error) from rpc_error
        finally:
            watchdog.stop()

    def _abort(self, file_handle: bytes, lease_id: str) -> None:
        request = metadata_pb2.AbortFileRequest(request_id=_request_id(), file_handle=file_handle, lease_id=lease_id)
        try:
            self.metadata.call_rpc("AbortFile", request)
        except DfshaError as error:
            logger.warning("No se pudo abortar la escritura: %s", error.message)

    def _unlock(self, lease_id: str) -> None:
        request = metadata_pb2.UnlockBlocksRequest(request_id=_request_id(), lease_id=lease_id)
        try:
            self.metadata.call_rpc("UnlockBlocks", request)
        except DfshaError as error:
            logger.warning("No se pudo liberar el arrendamiento (caducará solo): %s", error.message)

    # ===== Ayudas de get =======================================================================

    def _download_block(
        self, location: common_pb2.BlockLocation, file_handle: bytes, failed_addrs: set[str] | None = None
    ) -> bytes:
        """Lee un bloque de una réplica al azar y verifica el hash de los metadatos; si falla, prueba otra.

        Si el token de lectura caducó (una lectura de más de 10 min), pide uno nuevo sobre el mismo
        descriptor y, por tanto, sobre la misma versión (§6.2). ``failed_addrs`` son las réplicas que ya
        fallaron en este mismo get: se prueban las últimas (E6, etapa 10).
        """
        failed_addrs = set() if failed_addrs is None else failed_addrs
        addrs = list(location.datanode_addrs)
        random.shuffle(addrs)
        addrs.sort(key=lambda addr: addr in failed_addrs)  # estable: las que fallaron, al final
        last_error: DfshaError | None = None
        token_refreshed = False
        for addr in addrs:
            try:
                data = self._read_replica(addr, location)
            except grpc.RpcError as rpc_error:
                last_error = DfshaError.from_rpc_error(rpc_error)
                # La llamada que falla es la propia excepción, y su traza retiene los marcos que la contienen:
                # un ciclo que solo libera el recolector cíclico. Sin romperlo, cada réplica fallida retenía el
                # bloque leído después, y un get de 1 GiB con un nodo caído agotó la memoria (etapa 9)
                rpc_error.__traceback__ = None
                if last_error.reason is Reason.BLOCK_TOKEN_INVALID and not token_refreshed:
                    token_refreshed = True
                    location = self._refresh_location(file_handle, location)
                    addrs.append(addr)  # se vuelve a intentar con el token nuevo
                    continue
                logger.warning("La réplica de %s en %s falló: %s", location.block_id, addr, last_error.message)
                failed_addrs.add(addr)
                continue
            if hashlib.sha256(data).digest() != location.block_sha256:
                # El hash que vale es el de los metadatos, no el del nodo (§4.5). El nodo solo la marca si la
                # verifica él (§8.5): un cliente no puede hacer borrar réplicas sanas
                logger.warning("La réplica de %s en %s no coincide con su hash", location.block_id, addr)
                self._report_corrupt(location.block_id, addr)
                last_error = DfshaError(grpc.StatusCode.DATA_LOSS, "Réplica corrupta", Reason.BLOCK_CORRUPTED)
                continue
            return data
        raise DfshaError(
            grpc.StatusCode.DATA_LOSS,
            f"No se pudo leer el bloque {location.block_index} de ninguna réplica",
            Reason.BLOCK_LOST,
        ) from last_error

    def _read_replica(self, addr: str, location: common_pb2.BlockLocation) -> bytes:
        """Lee una réplica entera; si falla, lanza la propia llamada de gRPC como excepción.

        Si pasan ``transfer_inactivity_s`` sin ningún mensaje, se cancela la llamada: un nodo congelado acepta la
        conexión y no responde, y sin esto se esperaba el plazo de transferencia completo (E6, etapa 10).
        """
        responses = get_datanode_stub(self._channels, addr).ReadBlock(
            datanode_pb2.ReadBlockRequest(block_id=location.block_id, block_token=location.block_token),
            timeout=self.settings.transfer_timeout_s,
        )
        watchdog = _InactivityWatchdog(responses.cancel, self.settings.transfer_inactivity_s)
        try:
            pieces = []
            for response in responses:  # la primera es la cabecera
                watchdog.reset()
                if response.WhichOneof("content") == "data":
                    pieces.append(response.data)
            return b"".join(pieces)
        finally:
            watchdog.stop()

    def _report_corrupt(self, block_id: str, addr: str) -> None:
        request = metadata_pb2.ReportCorruptReplicaRequest(block_id=block_id, node_id=addr)
        try:
            self.metadata.call_rpc("ReportCorruptReplica", request)
        except DfshaError as error:
            logger.warning("No se pudo avisar de la réplica corrupta: %s", error.message)

    def _refresh_location(self, file_handle: bytes, location: common_pb2.BlockLocation) -> common_pb2.BlockLocation:
        request = metadata_pb2.GetBlockLocationsRequest(
            file_handle=file_handle,
            block_range=common_pb2.BlockRange(first_block_index=location.block_index, block_count=1),
        )
        return self.metadata.call_rpc("GetBlockLocations", request).locations[0]
