"""Biblioteca de cliente: operaciones de RF1 y RF2 sobre los RPC de metadatos y de datos (§3.5, §6)."""

import hashlib
import logging
import os
import random
import threading
import time
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import grpc

from dfsha.client.connection import ChannelPool, MetadataConnection, RetryPolicy, get_datanode_stub
from dfsha.common import config
from dfsha.common.errors import DfshaError, Reason
from dfsha.v1 import common_pb2, datanode_pb2, metadata_pb2

logger = logging.getLogger(__name__)

CHUNK_SIZE_BYTES = 1024 * 1024  # mensajes de 1 MiB (§5.2)
WHOLE_FILE = common_pb2.BlockRange(first_block_index=0, block_count=0)
MAX_BLOCKS_PER_ALLOCATION = 1024
MAX_BLOCK_ATTEMPTS = 4


@dataclass(frozen=True)
class ClientSettings:
    metadata_addrs: list[str]
    rpc_timeout_s: float = 10.0
    transfer_timeout_s: float = 120.0
    parallel_transfers: int = 4
    retry: RetryPolicy = field(default_factory=RetryPolicy)


def load_settings() -> ClientSettings:
    """Lee la configuración de las variables DFSHA_* (convenciones §2)."""
    return ClientSettings(
        metadata_addrs=config.get_addrs("METADATA_ADDRS"),
        rpc_timeout_s=config.get_float("RPC_TIMEOUT_S", 10.0),
        transfer_timeout_s=config.get_float("TRANSFER_TIMEOUT_S", 120.0),
        parallel_transfers=config.get_int("PARALLEL_TRANSFERS", 4),
        retry=RetryPolicy(max_attempts=config.get_int("MAX_ATTEMPTS", 8)),
    )


def _request_id() -> str:
    return str(uuid.uuid4())


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
                self._client.metadata.call(lambda stub, timeout: stub.UpdateLease(request, timeout=timeout))
            except DfshaError as error:
                self.error = error  # la confirmación fallará con LEASE_EXPIRED si de verdad caducó
                return

    def stop(self) -> None:
        self._stopped.set()
        self._thread.join(timeout=5)


class DfshaClient:
    def __init__(self, settings: ClientSettings) -> None:
        self.settings = settings
        self._channels = ChannelPool()
        self.metadata = MetadataConnection(settings.metadata_addrs, self._channels, settings.rpc_timeout_s, settings.retry)

    def close(self) -> None:
        self._channels.close()

    def __enter__(self) -> "DfshaClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ===== RF1: espacio de nombres =============================================================

    def list_directory(self, path: str) -> list[metadata_pb2.DirectoryEntry]:
        request = metadata_pb2.ListDirectoryRequest(path=path)
        return list(self.metadata.call(lambda stub, timeout: stub.ListDirectory(request, timeout=timeout)).entries)

    def get_file_info(self, path: str) -> metadata_pb2.FileInfo:
        request = metadata_pb2.GetFileInfoRequest(path=path)
        return self.metadata.call(lambda stub, timeout: stub.GetFileInfo(request, timeout=timeout)).info

    def create_directory(self, path: str) -> None:
        request = metadata_pb2.CreateDirectoryRequest(request_id=_request_id(), path=path)
        self.metadata.call(lambda stub, timeout: stub.CreateDirectory(request, timeout=timeout))

    def delete_directory(self, path: str) -> None:
        request = metadata_pb2.DeleteDirectoryRequest(request_id=_request_id(), path=path)
        self.metadata.call(lambda stub, timeout: stub.DeleteDirectory(request, timeout=timeout))

    def delete_file(self, path: str) -> None:
        request = metadata_pb2.DeleteFileRequest(request_id=_request_id(), path=path)
        self.metadata.call(lambda stub, timeout: stub.DeleteFile(request, timeout=timeout))

    def move(self, source_path: str, target_path: str) -> None:
        request = metadata_pb2.MovePathRequest(request_id=_request_id(), source_path=source_path, target_path=target_path)
        self.metadata.call(lambda stub, timeout: stub.MovePath(request, timeout=timeout))

    # ===== RF2: carga y recuperación ===========================================================

    def put(self, local_path: Path, remote_path: str) -> int:
        """Carga un archivo completo: creación si no existe, reemplazo si existe (§6.1). Devuelve la versión."""
        size_bytes = local_path.stat().st_size
        opened, write_mode = self._open_for_put(remote_path)
        block_size = opened.info.block_size_bytes
        block_count = -(-size_bytes // block_size) if size_bytes else 0
        lock_request = metadata_pb2.LockBlocksRequest(request_id=_request_id(), file_handle=opened.file_handle, block_range=WHOLE_FILE)
        lease = self.metadata.call(lambda stub, timeout: stub.LockBlocks(lock_request, timeout=timeout))
        ttl_s = max(1.0, lease.expires_at.ToNanoseconds() / 1e9 - time.time())
        keeper = _LeaseKeeper(self, lease.lease_id, renew_every_s=ttl_s / 3)
        committed: list[metadata_pb2.CommittedBlock] = []
        try:
            with open(local_path, "rb") as source:
                committed = self._upload_blocks(opened.file_handle, lease.lease_id, source.fileno(), block_size, block_count, size_bytes)
            commit_request = metadata_pb2.CommitFileRequest(
                request_id=_request_id(),
                file_handle=opened.file_handle,
                lease_id=lease.lease_id,
                write_mode=write_mode,
                blocks=committed,
                size_bytes=size_bytes,
            )
            return self.metadata.call(lambda stub, timeout: stub.CommitFile(commit_request, timeout=timeout)).version
        except BaseException:
            self._abort(opened.file_handle, lease.lease_id)
            raise
        finally:
            keeper.stop()
            self._unlock(lease.lease_id)

    def get(self, remote_path: str, local_path: Path) -> int:
        """Recupera la versión confirmada completa de un archivo (§6.2). Devuelve su tamaño."""
        open_request = metadata_pb2.OpenFileRequest(path=remote_path, mode=metadata_pb2.OPEN_MODE_READ)
        opened = self.metadata.call(lambda stub, timeout: stub.OpenFile(open_request, timeout=timeout))
        locate_request = metadata_pb2.GetBlockLocationsRequest(file_handle=opened.file_handle, block_range=WHOLE_FILE)
        locations = self.metadata.call(lambda stub, timeout: stub.GetBlockLocations(locate_request, timeout=timeout)).locations
        block_size = opened.info.block_size_bytes
        partial_path = local_path.with_name(local_path.name + ".dfsha-parcial")
        with open(partial_path, "wb") as target:
            descriptor = target.fileno()

            def fetch(location: common_pb2.BlockLocation) -> None:
                data = self._download_block(location)
                os.pwrite(descriptor, data, location.block_index * block_size)

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
                    return self.metadata.call(lambda stub, timeout: stub.OpenFile(request, timeout=timeout)), write_mode
                except DfshaError as error:
                    if error.reason not in (Reason.PATH_ALREADY_EXISTS, Reason.PATH_NOT_FOUND) or (
                        error.reason is Reason.PATH_NOT_FOUND and mode == metadata_pb2.OPEN_MODE_CREATE
                    ):
                        raise
        raise DfshaError(grpc.StatusCode.ABORTED, f"{remote_path} cambia demasiado deprisa; vuelve a intentarlo")

    def _allocate(self, file_handle: bytes, lease_id: str, indices: list[int]) -> list[common_pb2.BlockLocation]:
        locations: list[common_pb2.BlockLocation] = []
        for start in range(0, len(indices), MAX_BLOCKS_PER_ALLOCATION):
            request = metadata_pb2.AllocateBlocksRequest(
                request_id=_request_id(), file_handle=file_handle, lease_id=lease_id,
                block_indices=indices[start : start + MAX_BLOCKS_PER_ALLOCATION],
            )  # fmt: skip
            locations.extend(self.metadata.call(lambda stub, timeout: stub.AllocateBlocks(request, timeout=timeout)).blocks)
        return locations

    def _upload_blocks(
        self, file_handle: bytes, lease_id: str, descriptor: int, block_size: int, block_count: int, size_bytes: int
    ) -> list[metadata_pb2.CommittedBlock]:
        if not block_count:
            return []
        locations = self._allocate(file_handle, lease_id, list(range(block_count)))

        def upload(location: common_pb2.BlockLocation) -> metadata_pb2.CommittedBlock:
            offset = location.block_index * block_size
            data = os.pread(descriptor, min(block_size, size_bytes - offset), offset)
            sha256 = hashlib.sha256(data).digest()  # etapa 6: se cifra antes y el hash es del bloque cifrado
            for attempt in range(MAX_BLOCK_ATTEMPTS):
                try:
                    self._write_block(location, data, sha256)
                    return metadata_pb2.CommittedBlock(
                        block_index=location.block_index, block_id=location.block_id, block_sha256=sha256, size_bytes=len(data)
                    )
                except DfshaError as error:
                    if attempt == MAX_BLOCK_ATTEMPTS - 1:
                        raise
                    # Se repite el bloque en otros nodos, con un block_id nuevo (§11.3)
                    logger.warning("El bloque %d falló en %s (%s); se reserva de nuevo", location.block_index, location.datanode_addrs[0], error.message)
                    time.sleep(self.settings.retry.get_backoff_s(attempt))
                    location = self._allocate(file_handle, lease_id, [location.block_index])[0]
            raise AssertionError("inalcanzable")

        with ThreadPoolExecutor(self.settings.parallel_transfers) as pool:
            return list(pool.map(upload, locations))

    def _write_block(self, location: common_pb2.BlockLocation, data: bytes, sha256: bytes) -> None:
        primary, *secondaries = location.datanode_addrs

        def requests() -> Iterator[datanode_pb2.WriteBlockRequest]:
            header = datanode_pb2.WriteBlockHeader(
                block_id=location.block_id, block_token=location.block_token, block_sha256=sha256,
                size_bytes=len(data), secondary_addrs=secondaries,
            )  # fmt: skip
            yield datanode_pb2.WriteBlockRequest(header=header)
            for offset in range(0, len(data), CHUNK_SIZE_BYTES):
                yield datanode_pb2.WriteBlockRequest(data=data[offset : offset + CHUNK_SIZE_BYTES])

        try:
            get_datanode_stub(self._channels, primary).WriteBlock(requests(), timeout=self.settings.transfer_timeout_s)
        except grpc.RpcError as rpc_error:
            raise DfshaError.from_rpc_error(rpc_error) from rpc_error

    def _abort(self, file_handle: bytes, lease_id: str) -> None:
        request = metadata_pb2.AbortFileRequest(request_id=_request_id(), file_handle=file_handle, lease_id=lease_id)
        try:
            self.metadata.call(lambda stub, timeout: stub.AbortFile(request, timeout=timeout))
        except DfshaError as error:
            logger.warning("No se pudo abortar la escritura: %s", error.message)

    def _unlock(self, lease_id: str) -> None:
        request = metadata_pb2.UnlockBlocksRequest(request_id=_request_id(), lease_id=lease_id)
        try:
            self.metadata.call(lambda stub, timeout: stub.UnlockBlocks(request, timeout=timeout))
        except DfshaError as error:
            logger.warning("No se pudo liberar el arrendamiento (caducará solo): %s", error.message)

    # ===== Ayudas de get =======================================================================

    def _download_block(self, location: common_pb2.BlockLocation) -> bytes:
        """Lee un bloque de una réplica al azar y verifica el hash de los metadatos; si falla, prueba otra."""
        addrs = list(location.datanode_addrs)
        random.shuffle(addrs)
        last_error: DfshaError | None = None
        for addr in addrs:
            try:
                responses = get_datanode_stub(self._channels, addr).ReadBlock(
                    datanode_pb2.ReadBlockRequest(block_id=location.block_id, block_token=location.block_token),
                    timeout=self.settings.transfer_timeout_s,
                )
                next(responses)  # cabecera
                data = b"".join(response.data for response in responses)
            except grpc.RpcError as rpc_error:
                last_error = DfshaError.from_rpc_error(rpc_error)
                logger.warning("La réplica de %s en %s falló: %s", location.block_id, addr, last_error.message)
                continue
            if hashlib.sha256(data).digest() != location.block_sha256:
                # El hash que vale es el de los metadatos, no el del nodo (§4.5). El aviso llega en la etapa 9.
                logger.warning("La réplica de %s en %s no coincide con su hash", location.block_id, addr)
                last_error = DfshaError(grpc.StatusCode.DATA_LOSS, "Réplica corrupta", Reason.BLOCK_CORRUPTED)
                continue
            return data
        raise DfshaError(
            grpc.StatusCode.DATA_LOSS,
            f"No se pudo leer el bloque {location.block_index} de ninguna réplica",
            Reason.BLOCK_LOST,
        ) from last_error
