"""Lectura del modelo de metadatos en etcd: registros y resolución de rutas (ADR 0041)."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TypeVar

import grpc
from google.protobuf.message import Message

from dfsha.common.errors import DfshaError, Reason
from dfsha.etcd import rpc_pb2
from dfsha.etcd.rpc_pb2 import KeyValue
from dfsha.metadata.etcd_client import EtcdClient, get_prefix_end
from dfsha.metadata.keys import ROOT_DIRECTORY_ID, Keys
from dfsha.metadata.paths import split_path
from dfsha.v1 import metadata_pb2
from dfsha.v1.records_pb2 import EntryRecord

M = TypeVar("M", bound=Message)

_READS_PER_TXN = 100  # por debajo del límite de 128 operaciones por transacción de etcd


def parse(message_type: type[M], kv: KeyValue | None) -> M | None:
    if kv is None:
        return None
    return message_type.FromString(kv.value)


@dataclass
class Resolution:
    """Resultado de resolver una ruta en una revisión de etcd."""

    path: str
    directory_id: str                   # directorio que contiene la entrada final (o la raíz)
    name: str | None                    # nombre final; None si la ruta es la raíz
    entry: EntryRecord | None           # None si no existe (o si es la raíz)
    entry_kv: KeyValue | None
    revision: int
    parent_entry_key: bytes = b""       # entrada del directorio padre; vacía si el padre es la raíz
    parent_create_revision: int = 0
    ancestor_ids: list[str] = field(default_factory=list)  # de la raíz al padre, ambos incluidos

    @property
    def is_root(self) -> bool:
        return self.name is None

    @property
    def is_directory(self) -> bool:
        return self.is_root or (self.entry is not None and self.entry.type == metadata_pb2.ENTRY_TYPE_DIRECTORY)

    @property
    def is_file(self) -> bool:
        return self.entry is not None and self.entry.type == metadata_pb2.ENTRY_TYPE_FILE

    @property
    def target_directory_id(self) -> str:
        """Identificador del directorio al que apunta la ruta."""
        if self.is_root:
            return ROOT_DIRECTORY_ID
        assert self.entry is not None and self.is_directory
        return self.entry.target_id


class MetadataStore:
    def __init__(self, etcd: EtcdClient, keys: Keys) -> None:
        self.etcd = etcd
        self.keys = keys

    def get(self, message_type: type[M], key: bytes, revision: int = 0) -> tuple[M | None, KeyValue | None, int]:
        kv, read_revision = self.etcd.get(key, revision)
        return parse(message_type, kv), kv, read_revision

    def get_prefixes(self, prefixes: Sequence[bytes]) -> list[list[KeyValue]]:
        """Lee varios rangos por prefijo en transacciones de solo lectura, cada una en una sola revisión."""
        results: list[list[KeyValue]] = []
        for start in range(0, len(prefixes), _READS_PER_TXN):
            chunk = prefixes[start : start + _READS_PER_TXN]
            reads = [
                rpc_pb2.RequestOp(request_range=rpc_pb2.RangeRequest(key=prefix, range_end=get_prefix_end(prefix)))
                for prefix in chunk
            ]
            response = self.etcd.txn([], reads)
            results.extend(list(item.response_range.kvs) for item in response.responses)
        return results

    def get_keys(self, keys: Sequence[bytes]) -> list[KeyValue | None]:
        """Lee varias claves sueltas; None en las que no existen."""
        results: list[KeyValue | None] = []
        for start in range(0, len(keys), _READS_PER_TXN):
            chunk = keys[start : start + _READS_PER_TXN]
            reads = [rpc_pb2.RequestOp(request_range=rpc_pb2.RangeRequest(key=key)) for key in chunk]
            response = self.etcd.txn([], reads)
            results.extend(item.response_range.kvs[0] if item.response_range.kvs else None for item in response.responses)
        return results

    def resolve(self, user_id: str, path: str) -> Resolution:
        """Resuelve una ruta entrada a entrada, todas las lecturas en la misma revisión.

        Falla con PATH_NOT_FOUND si falta un directorio intermedio; la entrada final puede no existir.
        """
        components = split_path(path)
        directory_id = ROOT_DIRECTORY_ID
        ancestors = [ROOT_DIRECTORY_ID]
        parent_entry_key = b""
        parent_create_revision = 0
        revision = 0
        for name in components[:-1]:
            entry, kv, read_revision = self.get(EntryRecord, self.keys.entry(user_id, directory_id, name), revision)
            revision = revision or read_revision
            if entry is None or kv is None or entry.type != metadata_pb2.ENTRY_TYPE_DIRECTORY:
                raise path_not_found(path)
            directory_id = entry.target_id
            ancestors.append(directory_id)
            parent_entry_key = kv.key
            parent_create_revision = kv.create_revision
        if not components:
            _, revision = self.etcd.get(self.keys.leader)  # solo para fijar la revisión
            return Resolution(path, ROOT_DIRECTORY_ID, None, None, None, revision, ancestor_ids=[ROOT_DIRECTORY_ID])
        name = components[-1]
        entry, kv, read_revision = self.get(EntryRecord, self.keys.entry(user_id, directory_id, name), revision)
        return Resolution(
            path, directory_id, name, entry, kv, revision or read_revision,
            parent_entry_key, parent_create_revision, ancestors,
        )  # fmt: skip


def path_not_found(path: str) -> DfshaError:
    return DfshaError(grpc.StatusCode.NOT_FOUND, f"No existe {path}", Reason.PATH_NOT_FOUND)
