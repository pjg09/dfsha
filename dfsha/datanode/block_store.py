"""Almacén de bloques de un nodo de datos (fase I §3.4 y §8.4, ADR 0026).

Organización del directorio de datos:

- ``dfsha-node-id``: marca con el ``node_id`` del nodo. Sin ella el nodo no arranca.
- ``blocks/<2 primeros caracteres>/<block_id>``: el bloque, tal como llega (cifrado).
- ``blocks/<...>/<block_id>.meta``: su hash SHA-256 y su tamaño, para servirlos sin leer el bloque.
- ``staging/``: área temporal. Un bloque solo pasa al almacén con un renombrado atómico, después de
  ``fsync`` y de verificar su hash. Lo que queda en ``staging/`` nunca cuenta como réplica.
"""

import hashlib
import json
import logging
import os
import shutil
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

import grpc

from dfsha.common.errors import DfshaError, Reason

logger = logging.getLogger(__name__)

NODE_ID_MARKER = "dfsha-node-id"
_BLOCKS_DIRECTORY = "blocks"
_STAGING_DIRECTORY = "staging"
_META_SUFFIX = ".meta"


class DataDirectoryError(RuntimeError):
    """El directorio de datos no es seguro para escribir: el nodo no debe arrancar."""


@dataclass(frozen=True)
class BlockMeta:
    block_id: str
    sha256: bytes
    size_bytes: int


def validate_block_id(block_id: str) -> str:
    """Acepta solo UUID canónicos (fase I §4.2), que además son nombres de archivo seguros."""
    try:
        canonical: str | None = str(uuid.UUID(block_id))
    except ValueError:
        canonical = None
    if canonical is None or canonical != block_id:
        raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, f"block_id no válido: {block_id!r}")
    return block_id


def initialize_data_directory(data_directory: Path, node_id: str) -> None:
    """Escribe la marca con el node_id en un directorio de datos vacío.

    En AWS lo hace el script de despliegue después de montar el volumen EBS; en el entorno
    local, el propio nodo si se le pide expresamente.
    """
    marker = data_directory / NODE_ID_MARKER
    if marker.exists():
        return
    if any(data_directory.iterdir()):
        raise DataDirectoryError(f"{data_directory} no está vacío y no tiene la marca {NODE_ID_MARKER}")
    marker.write_text(node_id + "\n")
    _fsync_directory(data_directory)


def verify_data_directory(data_directory: Path, node_id: str, require_mount_point: bool) -> None:
    """Comprueba que el directorio de datos es el volumen de este nodo (fase I §3.4)."""
    if not data_directory.is_dir():
        raise DataDirectoryError(f"No existe el directorio de datos {data_directory}")
    if require_mount_point and not os.path.ismount(data_directory):
        raise DataDirectoryError(f"{data_directory} no es un punto de montaje: el volumen de datos no está montado")
    marker = data_directory / NODE_ID_MARKER
    if not marker.is_file():
        raise DataDirectoryError(f"{data_directory} no tiene la marca {NODE_ID_MARKER}")
    marked_node_id = marker.read_text().strip()
    if marked_node_id != node_id:
        raise DataDirectoryError(f"El volumen de datos es de {marked_node_id!r}, no de {node_id!r}")


class StagingBlock:
    """Bloque que se está recibiendo en el área temporal.

    Calcula el hash mientras se escribe y permite que otros hilos lean lo ya escrito
    (el reenvío a las secundarias, fase I §4.4) sin guardar el bloque en memoria.
    """

    def __init__(self, path: Path, block_id: str, expected_sha256: bytes, expected_size_bytes: int) -> None:
        self.path = path
        self.block_id = block_id
        self.expected_sha256 = expected_sha256
        self.expected_size_bytes = expected_size_bytes
        self._file = open(path, "wb")  # noqa: SIM115 (se cierra en finish() o discard())
        self._hasher = hashlib.sha256()
        self._written_bytes = 0
        self._is_finished = False
        self._is_failed = False
        self._condition = threading.Condition()

    @property
    def written_bytes(self) -> int:
        return self._written_bytes

    def append(self, data: bytes) -> None:
        if self._written_bytes + len(data) > self.expected_size_bytes:
            raise DfshaError(
                grpc.StatusCode.ABORTED,
                f"El bloque {self.block_id} trae más bytes de los anunciados ({self.expected_size_bytes})",
                Reason.BLOCK_CORRUPTED,
            )
        self._file.write(data)
        self._file.flush()  # que los lectores del archivo vean los datos
        self._hasher.update(data)
        with self._condition:
            self._written_bytes += len(data)
            self._condition.notify_all()

    def finish(self) -> BlockMeta:
        """Cierra la escritura y verifica tamaño y hash antes de confirmar el bloque (§8.4)."""
        self._file.flush()
        os.fsync(self._file.fileno())
        self._file.close()
        sha256 = self._hasher.digest()
        if self._written_bytes != self.expected_size_bytes or sha256 != self.expected_sha256:
            self.fail()
            raise DfshaError(
                grpc.StatusCode.ABORTED,
                f"El bloque {self.block_id} no coincide con su hash o su tamaño",
                Reason.BLOCK_CORRUPTED,
            )
        with self._condition:
            self._is_finished = True
            self._condition.notify_all()
        return BlockMeta(self.block_id, sha256, self._written_bytes)

    def fail(self) -> None:
        """Marca el bloque como fallido: los lectores pendientes se detienen."""
        if not self._file.closed:
            self._file.close()
        with self._condition:
            self._is_failed = True
            self._condition.notify_all()

    def wait_for_data(self, offset: int, timeout_s: float) -> int | None:
        """Espera a que haya datos más allá de ``offset``.

        Devuelve cuántos bytes hay escritos, 0 si el bloque terminó y no hay más,
        o None si falló o se agotó el plazo.
        """
        with self._condition:
            ready = self._condition.wait_for(
                lambda: self._written_bytes > offset or self._is_finished or self._is_failed,
                timeout=timeout_s,
            )
            if not ready or self._is_failed:
                return None
            if self._written_bytes > offset:
                return self._written_bytes
            return 0


class BlockStore:
    """Bloques confirmados y área temporal en el volumen de datos del nodo."""

    def __init__(self, data_directory: Path) -> None:
        self.data_directory = data_directory
        self._blocks_directory = data_directory / _BLOCKS_DIRECTORY
        self._staging_directory = data_directory / _STAGING_DIRECTORY
        self._blocks_directory.mkdir(exist_ok=True)
        self._staging_directory.mkdir(exist_ok=True)

    def clean_staging_area(self) -> int:
        """Borra los restos de escrituras interrumpidas. Se llama al arrancar."""
        removed = 0
        for path in self._staging_directory.iterdir():
            if path.is_file():
                path.unlink()
                removed += 1
        if removed:
            logger.info("Borrados %d bloques a medias del área temporal", removed)
        return removed

    def create_staging(self, block_id: str, expected_sha256: bytes, expected_size_bytes: int) -> StagingBlock:
        validate_block_id(block_id)
        path = self._staging_directory / f"{block_id}.{uuid.uuid4().hex}"
        return StagingBlock(path, block_id, expected_sha256, expected_size_bytes)

    def commit(self, staging: StagingBlock, meta: BlockMeta) -> bool:
        """Pasa un bloque verificado al almacén con un renombrado atómico.

        Devuelve False si el bloque ya estaba con el mismo hash (un reintento, Tabla 28 de la fase I). Si
        ya estaba con otro hash, lo rechaza: un ``block_id`` identifica siempre el mismo contenido.
        """
        block_path = self._get_block_path(meta.block_id)
        if block_path.exists():
            staging.path.unlink(missing_ok=True)
            _, stored = self.get_block(meta.block_id)
            if (stored.sha256, stored.size_bytes) != (meta.sha256, meta.size_bytes):
                raise DfshaError(
                    grpc.StatusCode.ALREADY_EXISTS, f"El bloque {meta.block_id} ya existe con otro contenido"
                )
            return False
        block_path.parent.mkdir(exist_ok=True)
        meta_path = block_path.with_name(block_path.name + _META_SUFFIX)
        meta_staging = staging.path.with_name(staging.path.name + _META_SUFFIX)
        meta_staging.write_text(json.dumps({"sha256": meta.sha256.hex(), "size_bytes": meta.size_bytes}))
        with open(meta_staging, "rb") as meta_file:
            os.fsync(meta_file.fileno())
        # Primero los metadatos: si existe el bloque, existen sus metadatos
        os.replace(meta_staging, meta_path)
        os.replace(staging.path, block_path)
        _fsync_directory(block_path.parent)
        return True

    def discard(self, staging: StagingBlock) -> None:
        staging.fail()
        staging.path.unlink(missing_ok=True)

    def get_block(self, block_id: str) -> tuple[Path, BlockMeta]:
        validate_block_id(block_id)
        block_path = self._get_block_path(block_id)
        meta_path = block_path.with_name(block_path.name + _META_SUFFIX)
        if not block_path.is_file() or not meta_path.is_file():
            raise DfshaError(grpc.StatusCode.NOT_FOUND, f"Este nodo de datos no tiene el bloque {block_id}")
        stored = json.loads(meta_path.read_text())
        return block_path, BlockMeta(block_id, bytes.fromhex(stored["sha256"]), int(stored["size_bytes"]))

    def get_free_bytes(self) -> int:
        return shutil.disk_usage(self.data_directory).free

    def get_capacity_bytes(self) -> int:
        return shutil.disk_usage(self.data_directory).total

    def list_blocks(self) -> list[BlockMeta]:
        """Todos los bloques confirmados del almacén, para el informe de bloques (ADR 0018)."""
        blocks = []
        for meta_path in self._blocks_directory.glob(f"*/*{_META_SUFFIX}"):
            block_id = meta_path.name.removesuffix(_META_SUFFIX)
            if not meta_path.with_name(block_id).is_file():
                continue  # metadatos de un bloque cuyo renombrado no llegó a hacerse
            stored = json.loads(meta_path.read_text())
            blocks.append(BlockMeta(block_id, bytes.fromhex(stored["sha256"]), int(stored["size_bytes"])))
        return blocks

    def _get_block_path(self, block_id: str) -> Path:
        return self._blocks_directory / block_id[:2] / block_id


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
