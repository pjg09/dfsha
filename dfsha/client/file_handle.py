"""Descriptor de archivo de RF3: open, read, write, lock, unlock y close (fase I §7 y §8).

Consistencia de apertura-cierre (§7.3): ``open()`` fija la versión que se lee y las escrituras se vuelven
visibles al confirmarse en ``close()``. ``write()`` arrienda en el momento el rango que toca, así que un
conflicto se ve enseguida (``LOCK_CONFLICT``), pero no envía nada: prepara los bloques afectados en un
archivo temporal local. ``close()`` los envía como bloques nuevos y confirma una versión nueva (§8.4).

Un descriptor no se comparte entre hilos.
"""

import logging
import os
import tempfile
import time
from typing import TYPE_CHECKING, BinaryIO

import grpc

from dfsha.common.errors import DfshaError
from dfsha.common.security import decrypt_block
from dfsha.v1 import common_pb2, metadata_pb2

if TYPE_CHECKING:
    from dfsha.client.client import DfshaClient, _LeaseKeeper

logger = logging.getLogger(__name__)

TO_END = 0  # block_count de un rango que llega hasta el final del archivo, aunque crezca
_WRITE_MODES_BY_OPEN_MODE = {
    metadata_pb2.OPEN_MODE_CREATE: (common_pb2.WRITE_MODE_CREATE,),
    metadata_pb2.OPEN_MODE_WRITE: (common_pb2.WRITE_MODE_REPLACE, common_pb2.WRITE_MODE_APPEND, common_pb2.WRITE_MODE_PARTIAL),
    metadata_pb2.OPEN_MODE_READ: (),
}


def _range_end(block_range: common_pb2.BlockRange) -> float:
    return float("inf") if block_range.block_count == TO_END else block_range.first_block_index + block_range.block_count


class FileHandle:
    def __init__(self, client: "DfshaClient", path: str, mode: metadata_pb2.OpenMode) -> None:
        self._client = client
        self.path = path
        self.mode = mode
        request = metadata_pb2.OpenFileRequest(path=path, mode=mode)
        self._opened: metadata_pb2.OpenFileResponse = client.metadata.call_rpc("OpenFile", request)
        self.version = self._opened.info.version  # la versión abierta; 0 si el archivo se crea al cerrar
        self.block_size = self._opened.info.block_size_bytes
        self._base_size = self._opened.info.size_bytes
        self.size = self._base_size  # tamaño con las escrituras propias sin confirmar
        self._locations: dict[int, common_pb2.BlockLocation] = {}
        self._cache: dict[int, bytes] = {}  # bloques en claro de la versión abierta (§7.1, L5)
        self._write_mode: common_pb2.WriteMode | None = None
        self._dirty: set[int] = set()
        self._staging: BinaryIO | None = None
        self._lease: metadata_pb2.LockBlocksResponse | None = None
        self._lease_range: common_pb2.BlockRange | None = None
        self._keeper: "_LeaseKeeper | None" = None
        self.closed = False

    # ===== RF3 =================================================================================

    def read(self, offset: int, length: int) -> bytes:
        """Lee hasta ``length`` bytes desde ``offset``: la versión abierta más las escrituras propias."""
        self._require_open()
        if offset < 0 or length < 0:
            raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "offset y longitud no pueden ser negativos")
        end = min(offset + length, self.size)
        if offset >= end:
            return b""
        pieces = []
        for index in range(offset // self.block_size, (end - 1) // self.block_size + 1):
            block_start = index * self.block_size
            block = self._get_block(index)
            pieces.append(block[max(offset - block_start, 0) : end - block_start])
        return b"".join(pieces)

    def write(self, data: bytes, offset: int = 0, mode: common_pb2.WriteMode | None = None) -> None:
        """Escribe ``data`` según el modo (Tabla 22): creación, reemplazo, anexado o modificación parcial.

        En anexado se ignora ``offset``: los datos van al final. Un ``offset`` más allá del final rellena
        el hueco con ceros. Cada apertura admite un solo modo de escritura.
        """
        self._require_open()
        write_mode = self._choose_write_mode(mode)
        if write_mode == common_pb2.WRITE_MODE_APPEND:
            offset = self.size
        if offset < 0:
            raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "offset no puede ser negativo")
        if self._write_mode is None and write_mode in (common_pb2.WRITE_MODE_CREATE, common_pb2.WRITE_MODE_REPLACE):
            self.size = self._base_size = 0  # crear y reemplazar parten de un archivo vacío
        needed = self._get_needed_range(write_mode, offset, len(data))
        if self._lease is None:
            self._acquire_lease(needed)
        elif not self._covers(needed):
            raise DfshaError(
                grpc.StatusCode.FAILED_PRECONDITION,
                "La escritura se sale del rango arrendado; usa lock() con el rango completo antes de escribir",
            )
        self._write_mode = write_mode
        self._stage(offset, data)

    def lock(self, first_block_index: int = 0, block_count: int = TO_END) -> None:
        """Arrienda un rango de bloques para agrupar varias escrituras (§8.1). Entero o nada."""
        self._require_open()
        self._require_writable()
        if self._lease is not None:
            raise DfshaError(grpc.StatusCode.FAILED_PRECONDITION, "Ya hay un arrendamiento; usa unlock() o close() antes")
        self._acquire_lease(common_pb2.BlockRange(first_block_index=first_block_index, block_count=block_count))

    def unlock(self) -> None:
        """Libera el arrendamiento. Las escrituras sin confirmar se confirman con close(), no aquí."""
        self._require_open()
        if self._dirty:
            raise DfshaError(grpc.StatusCode.FAILED_PRECONDITION, "Hay escrituras sin confirmar; usa close() para confirmarlas")
        self._release_lease()

    def close(self) -> int:
        """Confirma las escrituras como una versión nueva (§8.4) y cierra. Devuelve la versión vigente."""
        if self.closed:
            return self.version
        try:
            if self._write_mode is not None and self._lease is not None:
                self.version = self._commit()
        except BaseException:
            self.abort()
            raise
        self._finish()
        return self.version

    def abort(self) -> None:
        """Descarta las escrituras sin confirmar y cierra; sus bloques los borra la recolección de basura."""
        if self.closed:
            return
        if self._lease is not None and self._dirty:
            self._client._abort(self._opened.file_handle, self._lease.lease_id)
        self._finish()

    def __enter__(self) -> "FileHandle":
        return self

    def __exit__(self, exc_type: type[BaseException] | None, *_: object) -> None:
        if exc_type is None:
            self.close()
        else:
            self.abort()

    # ===== Lectura ==============================================================================

    def _get_block(self, index: int, size: int | None = None) -> bytes:
        """Contenido en claro de un bloque: el preparado si se escribió, si no el de la versión abierta."""
        size = self.size if size is None else size
        length = max(0, min(self.block_size, size - index * self.block_size))
        if length == 0:
            return b""
        if index in self._dirty:
            assert self._staging is not None
            return os.pread(self._staging.fileno(), length, index * self.block_size)
        base = self._get_base_block(index) if index * self.block_size < self._base_size else b""
        return base[:length].ljust(length, b"\0")

    def _get_base_block(self, index: int) -> bytes:
        cached = self._cache.get(index)
        if cached is not None:
            return cached
        location = self._locations.get(index)
        if location is None:
            self._load_locations(index)
            location = self._locations[index]
        stored = self._client._download_block(location, self._opened.file_handle)
        block = decrypt_block(self._opened.data_key, location.block_id, stored)
        self._cache[index] = block
        return block

    def _load_locations(self, first_index: int) -> None:
        """Ubica los bloques de la versión abierta desde ``first_index`` hasta el final (§6.2)."""
        request = metadata_pb2.GetBlockLocationsRequest(
            file_handle=self._opened.file_handle,
            block_range=common_pb2.BlockRange(first_block_index=first_index, block_count=TO_END),
        )
        for location in self._client.metadata.call_rpc("GetBlockLocations", request).locations:
            self._locations[location.block_index] = location

    # ===== Escritura ============================================================================

    def _choose_write_mode(self, mode: common_pb2.WriteMode | None) -> common_pb2.WriteMode:
        self._require_writable()
        allowed = _WRITE_MODES_BY_OPEN_MODE[self.mode]
        if mode is None:
            mode = self._write_mode or allowed[0]
        if mode not in allowed:
            raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "Ese modo de escritura no vale con el modo en que se abrió el archivo")
        if self._write_mode is not None and mode != self._write_mode:
            raise DfshaError(grpc.StatusCode.FAILED_PRECONDITION, "Cada apertura admite un solo modo de escritura; cierra antes de cambiarlo")
        return mode

    def _get_needed_range(self, write_mode: common_pb2.WriteMode, offset: int, length: int) -> common_pb2.BlockRange:
        """Rango que pide cada modo (Tabla 22)."""
        if write_mode in (common_pb2.WRITE_MODE_CREATE, common_pb2.WRITE_MODE_REPLACE):
            return common_pb2.BlockRange(first_block_index=0, block_count=TO_END)
        end = offset + length
        if end > self._base_size or write_mode == common_pb2.WRITE_MODE_APPEND:
            # Alarga el archivo: la cola, desde el último bloque de la versión abierta, que puede no estar lleno
            first = min(offset, self._base_size) // self.block_size
            return common_pb2.BlockRange(first_block_index=first, block_count=TO_END)
        first, last = offset // self.block_size, (max(end, offset + 1) - 1) // self.block_size
        return common_pb2.BlockRange(first_block_index=first, block_count=last - first + 1)

    def _covers(self, needed: common_pb2.BlockRange) -> bool:
        assert self._lease_range is not None
        return self._lease_range.first_block_index <= needed.first_block_index and _range_end(needed) <= _range_end(self._lease_range)

    def _stage(self, offset: int, data: bytes) -> None:
        """Aplica la escritura a los bloques que toca, en el archivo temporal (lectura, cambio y escritura)."""
        if not data:
            return
        if self._staging is None:
            self._staging = tempfile.TemporaryFile(prefix="dfsha-")
        staging = self._staging
        end = offset + len(data)
        new_size = max(self.size, end)
        first = offset // self.block_size
        if end > self.size:
            first = min(first, self.size // self.block_size)  # alarga: cambian el último bloque y los del hueco
        for index in range(first, (end - 1) // self.block_size + 1):
            block_start = index * self.block_size
            block = bytearray(self._get_block(index, self.size).ljust(min(self.block_size, new_size - block_start), b"\0"))
            start, stop = max(offset, block_start), min(end, block_start + self.block_size)
            if start < stop:
                block[start - block_start : stop - block_start] = data[start - offset : stop - offset]
            os.pwrite(staging.fileno(), bytes(block), block_start)
            self._dirty.add(index)
        self.size = new_size

    def _acquire_lease(self, block_range: common_pb2.BlockRange) -> None:
        from dfsha.client.client import _LeaseKeeper, _request_id

        request = metadata_pb2.LockBlocksRequest(request_id=_request_id(), file_handle=self._opened.file_handle, block_range=block_range)
        lease: metadata_pb2.LockBlocksResponse = self._client.metadata.call_rpc("LockBlocks", request)
        self._lease, self._lease_range = lease, block_range
        ttl_s = max(1.0, lease.expires_at.ToNanoseconds() / 1e9 - time.time())
        self._keeper = _LeaseKeeper(self._client, lease.lease_id, renew_every_s=ttl_s / 3)  # cada ~10 s

    def _release_lease(self) -> None:
        if self._keeper is not None:
            self._keeper.stop()
            self._keeper = None
        if self._lease is not None:
            self._client._unlock(self._lease.lease_id)
            self._lease = None
            self._lease_range = None

    def _commit(self) -> int:
        from dfsha.client.client import _request_id

        assert self._lease is not None and self._write_mode is not None
        if self._write_mode in (common_pb2.WRITE_MODE_CREATE, common_pb2.WRITE_MODE_REPLACE):
            indices = list(range(-(-self.size // self.block_size)))  # el contenido entero es nuevo
        else:
            indices = sorted(self._dirty)
        committed = self._client._upload_blocks(
            self._opened.file_handle, self._opened.data_key, self._lease.lease_id, indices, self._get_block
        )
        request = metadata_pb2.CommitFileRequest(
            request_id=_request_id(),
            file_handle=self._opened.file_handle,
            lease_id=self._lease.lease_id,
            write_mode=self._write_mode,
            blocks=committed,
            size_bytes=self.size,
        )
        return self._client.metadata.call_rpc("CommitFile", request).version

    # ===== Estado ===============================================================================

    def _require_open(self) -> None:
        if self.closed:
            raise DfshaError(grpc.StatusCode.FAILED_PRECONDITION, "El archivo ya está cerrado")

    def _require_writable(self) -> None:
        if self.mode == metadata_pb2.OPEN_MODE_READ:
            raise DfshaError(grpc.StatusCode.FAILED_PRECONDITION, "El archivo está abierto solo para leer")

    def _finish(self) -> None:
        self._release_lease()
        if self._staging is not None:
            self._staging.close()
            self._staging = None
        self._dirty.clear()
        self._cache.clear()
        self.closed = True
