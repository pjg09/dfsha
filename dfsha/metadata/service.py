"""Servicio MetadataService sobre etcd (fase I §5.2, §6 y §8; ADR 0039 y 0041).

Todas las escrituras siguen el mismo camino (``_mutate``): una sola transacción de etcd que compara la
época del líder (cercado), que el ``request_id`` es nuevo y que lo leído no ha cambiado. Si otra escritura
se cruza, se vuelve a leer y a calcular. La respuesta queda guardada 10 min para los reintentos (§8.6).
"""

import logging
import threading
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TypeVar

import grpc
from google.protobuf.message import Message
from google.protobuf.timestamp_pb2 import Timestamp

from dfsha.common.config import ConfigError, parse_addr
from dfsha.common.errors import DfshaError, Reason
from dfsha.etcd.rpc_pb2 import Compare, RequestOp
from dfsha.metadata.etcd_client import (
    EtcdError,
    compare_absent,
    compare_create_revision,
    compare_mod_revision,
    compare_prefix_empty,
    op_delete,
    op_delete_prefix,
    op_put,
)
from dfsha.metadata.keys import ROOT_DIRECTORY_ID
from dfsha.metadata.leader import LeaderElection, NotLeaderError
from dfsha.metadata.nodes import NodeRegistry, NodeState
from dfsha.metadata.store import MetadataStore, Resolution, parse, path_not_found
from dfsha.v1 import common_pb2, metadata_pb2, metadata_pb2_grpc
from dfsha.v1.records_pb2 import (
    EntryRecord,
    FileHandle,
    FileRecord,
    LeaseRecord,
    NodeRecord,
    PendingRecord,
    ReplicaRecord,
    VersionRecord,
)

logger = logging.getLogger(__name__)

R = TypeVar("R", bound=Message)

IMPLICIT_USER_ID = "local"  # único usuario hasta la etapa 6 (ADR 0041)
MAX_MUTATION_ATTEMPTS = 8
MAX_BLOCKS_PER_ALLOCATION = 4096
_OPS_PER_TXN = 100


@dataclass(frozen=True)
class MetadataSettings:
    addr: str
    block_size_bytes: int = 16 * 1024 * 1024
    replication_factor: int = 3
    write_quorum: int = 2
    lease_ttl_s: int = 30
    grace_period_s: int = 600
    request_ttl_s: int = 600


@dataclass
class _Plan:
    """Lo que una escritura quiere aplicar si lo leído no ha cambiado."""

    compares: list[Compare]
    ops: list[RequestOp]
    response: Message
    on_success: Callable[[], None] | None = None


@dataclass
class _LeaseView:
    leases: list[tuple[LeaseRecord, bytes]] = field(default_factory=list)  # (registro, clave)
    guard_mod_revision: int = 0
    guard_value: int = 0


class _RequestLog:
    """Arrendamiento de etcd al que se ligan las respuestas guardadas; caducan solas (§8.6)."""

    def __init__(self, service: "MetadataService", ttl_s: int) -> None:
        self._service = service
        self._ttl_s = ttl_s
        self._lock = threading.Lock()
        self._lease_id = 0
        self._granted_at = 0.0

    def get_lease_id(self) -> int:
        with self._lock:
            if not self._lease_id or time.monotonic() - self._granted_at > 60:
                # Un arrendamiento nuevo cada minuto: cada respuesta vive entre ttl_s y ttl_s + 60 s
                self._lease_id = self._service.store.etcd.grant_lease(self._ttl_s + 60)
                self._granted_at = time.monotonic()
            return self._lease_id


def _now_timestamp(seconds: float) -> Timestamp:
    timestamp = Timestamp()
    timestamp.FromNanoseconds(int(seconds * 1e9))
    return timestamp


def _timestamp_seconds(timestamp: Timestamp) -> float:
    return timestamp.ToNanoseconds() / 1e9


def _range_end(block_range: common_pb2.BlockRange) -> float:
    return float("inf") if block_range.block_count == 0 else block_range.first_block_index + block_range.block_count


def _ranges_overlap(first: common_pb2.BlockRange, second: common_pb2.BlockRange) -> bool:
    return first.first_block_index < _range_end(second) and second.first_block_index < _range_end(first)


def _range_contains(block_range: common_pb2.BlockRange, block_index: int) -> bool:
    return block_range.first_block_index <= block_index < _range_end(block_range)


class MetadataService(metadata_pb2_grpc.MetadataServiceServicer):
    def __init__(
        self,
        settings: MetadataSettings,
        store: MetadataStore,
        election: LeaderElection,
        registry: NodeRegistry,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        self.settings = settings
        self.store = store
        self.keys = store.keys
        self.election = election
        self.registry = registry
        self._wall_clock = wall_clock
        self._request_log = _RequestLog(self, settings.request_ttl_s)

    def on_elected(self, epoch: int) -> None:
        """Al ser elegido, carga los nodos registrados; ninguno cuenta como vivo hasta su latido (§9.5)."""
        kvs, _ = self.store.etcd.get_prefix(self.keys.nodes_prefix)
        self.registry.reset_for_election(NodeRecord.FromString(kv.value) for kv in kvs)
        logger.info("Líder con época %d; %d nodos de datos registrados", epoch, len(kvs))

    # ===== Infraestructura =====================================================================

    def _handle(self, context: grpc.ServicerContext, operation: Callable[[], R]) -> R:
        try:
            if not self.election.is_leader:
                raise NotLeaderError(self.election.get_leader_addr())
            return operation()
        except NotLeaderError as error:
            failure = DfshaError(
                grpc.StatusCode.UNAVAILABLE,
                "Este servidor de metadatos no es el líder",
                Reason.NODE_NOT_LEADER,
                {"leader_addr": error.leader_addr},
            )
        except DfshaError as error:
            failure = error
        except EtcdError as error:
            logger.warning("etcd no responde: %s", error)
            failure = DfshaError(grpc.StatusCode.UNAVAILABLE, "El almacén de metadatos no responde")
        context.abort_with_status(failure.to_status())

    def _get_user_id(self, context: grpc.ServicerContext) -> str:
        return IMPLICIT_USER_ID  # etapa 6: el usuario del token de acceso

    def _now(self) -> float:
        return self._wall_clock()

    def _mutate(self, user_id: str, request_id: str, response_type: type[R], build: Callable[[], _Plan]) -> R:
        """Aplica una escritura de forma atómica e idempotente (§8.4, §8.6)."""
        if not request_id:
            raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "Falta el request_id")
        request_key = self.keys.request(user_id, request_id)
        for _ in range(MAX_MUTATION_ATTEMPTS):
            stored, _, _ = self.store.get(response_type, request_key)
            if stored is not None:
                return stored  # reintento de una petición ya aplicada: la misma respuesta
            plan = build()
            fencing = self.election.fencing_compare()
            store_response = op_put(request_key, plan.response.SerializeToString(), self._request_log.get_lease_id())
            result = self.store.etcd.txn([fencing, compare_absent(request_key), *plan.compares], [*plan.ops, store_response])
            if result.succeeded:
                if plan.on_success is not None:
                    plan.on_success()
                assert isinstance(plan.response, response_type)
                return plan.response
            self._verify_still_leader()
        raise DfshaError(grpc.StatusCode.ABORTED, "Demasiadas escrituras simultáneas sobre los mismos metadatos; reintenta")

    def _apply_without_request(self, compares: Sequence[Compare], ops: Sequence[RequestOp]) -> bool:
        """Escritura del líder sin request_id (avisos de los nodos de datos), con cercado."""
        result = self.store.etcd.txn([self.election.fencing_compare(), *compares], list(ops))
        if not result.succeeded:
            self._verify_still_leader()
        return result.succeeded

    def _verify_still_leader(self) -> None:
        kv, _ = self.store.etcd.get(self.keys.leader)
        epoch = self.election.epoch
        if kv is None or kv.create_revision != epoch:
            self.election.lose_leadership("la comparación de cercado falló")
            raise NotLeaderError(self.election.get_leader_addr())

    # ===== Espacio de nombres ==================================================================

    def ListDirectory(self, request: metadata_pb2.ListDirectoryRequest, context: grpc.ServicerContext) -> metadata_pb2.ListDirectoryResponse:  # noqa: N802
        def operation() -> metadata_pb2.ListDirectoryResponse:
            user_id = self._get_user_id(context)
            resolution = self.store.resolve(user_id, request.path)
            if resolution.is_file:
                assert resolution.name is not None and resolution.entry is not None
                return metadata_pb2.ListDirectoryResponse(entries=[self._build_entry(resolution.name, resolution.entry)])
            if not resolution.is_directory:
                raise path_not_found(request.path)
            prefix = self.keys.entries_prefix(user_id, resolution.target_directory_id)
            kvs, _ = self.store.etcd.get_prefix(prefix, revision=resolution.revision)
            entries = [(kv.key[len(prefix):].decode(), EntryRecord.FromString(kv.value)) for kv in kvs]
            file_ids = [entry.target_id for _, entry in entries if entry.type == metadata_pb2.ENTRY_TYPE_FILE]
            files = {
                record.file_id: record
                for kv in self.store.get_keys([self.keys.file(file_id) for file_id in file_ids])
                if (record := parse(FileRecord, kv)) is not None
            }
            return metadata_pb2.ListDirectoryResponse(
                entries=[self._build_entry(name, entry, files.get(entry.target_id)) for name, entry in entries]
            )

        return self._handle(context, operation)

    def GetFileInfo(self, request: metadata_pb2.GetFileInfoRequest, context: grpc.ServicerContext) -> metadata_pb2.GetFileInfoResponse:  # noqa: N802
        def operation() -> metadata_pb2.GetFileInfoResponse:
            user_id = self._get_user_id(context)
            resolution = self.store.resolve(user_id, request.path)
            file_record = self._get_file_of(resolution)
            return metadata_pb2.GetFileInfoResponse(info=self._build_file_info(request.path, file_record))

        return self._handle(context, operation)

    def CreateDirectory(self, request: metadata_pb2.CreateDirectoryRequest, context: grpc.ServicerContext) -> metadata_pb2.CreateDirectoryResponse:  # noqa: N802
        def build() -> _Plan:
            user_id = self._get_user_id(context)
            resolution = self.store.resolve(user_id, request.path)
            if resolution.is_root or resolution.entry is not None:
                raise DfshaError(grpc.StatusCode.ALREADY_EXISTS, f"Ya existe {request.path}", Reason.PATH_ALREADY_EXISTS)
            assert resolution.name is not None
            entry = EntryRecord(
                type=metadata_pb2.ENTRY_TYPE_DIRECTORY, target_id=uuid.uuid4().hex, modified_at=_now_timestamp(self._now())
            )
            key = self.keys.entry(user_id, resolution.directory_id, resolution.name)
            return _Plan(
                [*self._parent_exists(resolution), compare_absent(key)],
                [op_put(key, entry.SerializeToString())],
                metadata_pb2.CreateDirectoryResponse(),
            )

        return self._handle(context, lambda: self._mutate(self._get_user_id(context), request.request_id, metadata_pb2.CreateDirectoryResponse, build))

    def DeleteDirectory(self, request: metadata_pb2.DeleteDirectoryRequest, context: grpc.ServicerContext) -> metadata_pb2.DeleteDirectoryResponse:  # noqa: N802
        def build() -> _Plan:
            user_id = self._get_user_id(context)
            resolution = self.store.resolve(user_id, request.path)
            if resolution.is_root:
                raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "No se puede borrar la raíz", Reason.PATH_INVALID)
            if not resolution.is_directory or resolution.entry_kv is None:
                raise path_not_found(request.path)
            children = self.keys.entries_prefix(user_id, resolution.target_directory_id)
            if self.store.etcd.count_prefix(children, resolution.revision):
                raise DfshaError(grpc.StatusCode.FAILED_PRECONDITION, f"{request.path} no está vacío", Reason.DIRECTORY_NOT_EMPTY)
            return _Plan(
                [compare_mod_revision(resolution.entry_kv.key, resolution.entry_kv.mod_revision), compare_prefix_empty(children)],
                [op_delete(resolution.entry_kv.key)],
                metadata_pb2.DeleteDirectoryResponse(),
            )

        return self._handle(context, lambda: self._mutate(self._get_user_id(context), request.request_id, metadata_pb2.DeleteDirectoryResponse, build))

    def DeleteFile(self, request: metadata_pb2.DeleteFileRequest, context: grpc.ServicerContext) -> metadata_pb2.DeleteFileResponse:  # noqa: N802
        def build() -> _Plan:
            user_id = self._get_user_id(context)
            resolution = self.store.resolve(user_id, request.path)
            file_record = self._get_file_of(resolution)
            assert resolution.entry_kv is not None
            file_key = self.keys.file(file_record.file_id)
            _, file_kv, _ = self.store.get(FileRecord, file_key)
            view = self._read_leases(file_record.file_id)
            if any(self._is_lease_alive(lease) for lease, _ in view.leases):
                raise DfshaError(grpc.StatusCode.ABORTED, f"Alguien está escribiendo {request.path}", Reason.LOCK_CONFLICT)
            assert file_kv is not None
            now = self._now()
            deleted = FileRecord()
            deleted.CopyFrom(file_record)
            deleted.is_deleted = True
            deleted.modified_at.CopyFrom(_now_timestamp(now))
            ops = [op_delete(resolution.entry_kv.key), op_put(file_key, deleted.SerializeToString())]
            ops.extend(self._supersede_version(file_record, now))
            return _Plan(
                [
                    compare_mod_revision(resolution.entry_kv.key, resolution.entry_kv.mod_revision),
                    compare_mod_revision(file_key, file_kv.mod_revision),
                    compare_mod_revision(self.keys.lease_guard(file_record.file_id), view.guard_mod_revision),
                ],
                ops,
                metadata_pb2.DeleteFileResponse(),
            )

        return self._handle(context, lambda: self._mutate(self._get_user_id(context), request.request_id, metadata_pb2.DeleteFileResponse, build))

    def MovePath(self, request: metadata_pb2.MovePathRequest, context: grpc.ServicerContext) -> metadata_pb2.MovePathResponse:  # noqa: N802
        def build() -> _Plan:
            user_id = self._get_user_id(context)
            source = self.store.resolve(user_id, request.source_path)
            if source.is_root:
                raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "No se puede mover la raíz", Reason.PATH_INVALID)
            if source.entry is None or source.entry_kv is None:
                raise path_not_found(request.source_path)
            target = self.store.resolve(user_id, request.target_path)
            if target.is_root or target.entry is not None:
                raise DfshaError(grpc.StatusCode.ALREADY_EXISTS, f"Ya existe {request.target_path}", Reason.PATH_ALREADY_EXISTS)
            assert target.name is not None
            if source.is_directory and source.target_directory_id in target.ancestor_ids:
                raise DfshaError(
                    grpc.StatusCode.INVALID_ARGUMENT, "No se puede mover un directorio dentro de sí mismo", Reason.PATH_INVALID
                )
            moved = EntryRecord()
            moved.CopyFrom(source.entry)
            moved.modified_at.CopyFrom(_now_timestamp(self._now()))
            target_key = self.keys.entry(user_id, target.directory_id, target.name)
            return _Plan(
                [
                    compare_mod_revision(source.entry_kv.key, source.entry_kv.mod_revision),
                    *self._parent_exists(target),
                    compare_absent(target_key),
                ],
                [op_delete(source.entry_kv.key), op_put(target_key, moved.SerializeToString())],
                metadata_pb2.MovePathResponse(),
            )

        return self._handle(context, lambda: self._mutate(self._get_user_id(context), request.request_id, metadata_pb2.MovePathResponse, build))

    # ===== Acceso a archivos ===================================================================

    def OpenFile(self, request: metadata_pb2.OpenFileRequest, context: grpc.ServicerContext) -> metadata_pb2.OpenFileResponse:  # noqa: N802
        def operation() -> metadata_pb2.OpenFileResponse:
            user_id = self._get_user_id(context)
            resolution = self.store.resolve(user_id, request.path)
            if request.mode == metadata_pb2.OPEN_MODE_CREATE:
                if resolution.is_root or resolution.entry is not None:
                    raise DfshaError(grpc.StatusCode.ALREADY_EXISTS, f"Ya existe {request.path}", Reason.PATH_ALREADY_EXISTS)
                assert resolution.name is not None
                handle = FileHandle(
                    file_id=uuid.uuid4().hex,
                    version=0,
                    mode=request.mode,
                    user_id=user_id,
                    block_size_bytes=self.settings.block_size_bytes,
                    parent_directory_id=resolution.directory_id,
                    name=resolution.name,
                    parent_entry_key=resolution.parent_entry_key,
                    parent_create_revision=resolution.parent_create_revision,
                )
                info = metadata_pb2.FileInfo(
                    file_id=handle.file_id, path=request.path, block_size_bytes=handle.block_size_bytes
                )
                return metadata_pb2.OpenFileResponse(file_handle=handle.SerializeToString(), info=info)
            if request.mode not in (metadata_pb2.OPEN_MODE_READ, metadata_pb2.OPEN_MODE_WRITE):
                raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "Modo de apertura no válido")
            file_record = self._get_file_of(resolution)
            handle = FileHandle(
                file_id=file_record.file_id,
                version=file_record.current_version,
                mode=request.mode,
                user_id=user_id,
                block_size_bytes=file_record.block_size_bytes,
            )
            # La clave de datos llega en la etapa 6 (ADR 0024)
            return metadata_pb2.OpenFileResponse(
                file_handle=handle.SerializeToString(), info=self._build_file_info(request.path, file_record)
            )

        return self._handle(context, operation)

    def GetBlockLocations(self, request: metadata_pb2.GetBlockLocationsRequest, context: grpc.ServicerContext) -> metadata_pb2.GetBlockLocationsResponse:  # noqa: N802
        def operation() -> metadata_pb2.GetBlockLocationsResponse:
            handle = self._decode_handle(context, request.file_handle)
            if handle.version == 0:
                return metadata_pb2.GetBlockLocationsResponse()
            version = self._get_live_version(handle.file_id, handle.version)
            blocks = [
                block for block in version.blocks if _range_contains(request.block_range, block.block_index)
            ]
            replica_lists = self.store.get_prefixes([self.keys.replicas_prefix(block.block_id) for block in blocks])
            locations = []
            for block, replica_kvs in zip(blocks, replica_lists, strict=True):
                addrs = []
                for kv in replica_kvs:
                    replica = ReplicaRecord.FromString(kv.value)
                    if replica.is_corrupt or self.registry.get_state(replica.node_id) is NodeState.DEAD:
                        continue
                    addr = self.registry.get_addr(replica.node_id)
                    if addr is not None:
                        addrs.append(addr)
                # Los tokens de lectura llegan en la etapa 6 (ADR 0022)
                locations.append(
                    common_pb2.BlockLocation(
                        block_index=block.block_index,
                        block_id=block.block_id,
                        block_sha256=block.block_sha256,
                        size_bytes=block.size_bytes,
                        datanode_addrs=addrs,
                    )
                )
            return metadata_pb2.GetBlockLocationsResponse(locations=locations)

        return self._handle(context, operation)

    def LockBlocks(self, request: metadata_pb2.LockBlocksRequest, context: grpc.ServicerContext) -> metadata_pb2.LockBlocksResponse:  # noqa: N802
        def build() -> _Plan:
            user_id = self._get_user_id(context)
            handle = self._decode_handle(context, request.file_handle)
            self._require_write_handle(handle)
            view = self._read_leases(handle.file_id)
            if any(self._is_lease_alive(lease) and _ranges_overlap(lease.block_range, request.block_range) for lease, _ in view.leases):
                raise DfshaError(grpc.StatusCode.ABORTED, "Otro escritor tiene arrendado ese rango", Reason.LOCK_CONFLICT)
            now = self._now()
            lease = LeaseRecord(
                lease_id=f"{handle.file_id}.{uuid.uuid4().hex}",
                file_id=handle.file_id,
                user_id=user_id,
                block_range=request.block_range,
                expires_at=_now_timestamp(now + self.settings.lease_ttl_s),
            )
            current_version = 0
            if handle.version:
                file_record, _, _ = self.store.get(FileRecord, self.keys.file(handle.file_id))
                current_version = file_record.current_version if file_record is not None else 0
            ops = [op_put(self.keys.lease(handle.file_id, lease.lease_id), lease.SerializeToString())]
            ops.extend(self._delete_expired_leases(view))
            ops.append(self._bump_lease_guard(handle.file_id, view))
            return _Plan(
                [compare_mod_revision(self.keys.lease_guard(handle.file_id), view.guard_mod_revision)],
                ops,
                metadata_pb2.LockBlocksResponse(
                    lease_id=lease.lease_id, expires_at=lease.expires_at, current_version=current_version
                ),
            )

        return self._handle(context, lambda: self._mutate(self._get_user_id(context), request.request_id, metadata_pb2.LockBlocksResponse, build))

    def UpdateLease(self, request: metadata_pb2.UpdateLeaseRequest, context: grpc.ServicerContext) -> metadata_pb2.UpdateLeaseResponse:  # noqa: N802
        def build() -> _Plan:
            user_id = self._get_user_id(context)
            lease, key, mod_revision = self._get_valid_lease(user_id, request.lease_id)
            renewed = LeaseRecord()
            renewed.CopyFrom(lease)
            renewed.expires_at.CopyFrom(_now_timestamp(self._now() + self.settings.lease_ttl_s))
            return _Plan(
                [compare_mod_revision(key, mod_revision)],
                [op_put(key, renewed.SerializeToString())],
                metadata_pb2.UpdateLeaseResponse(expires_at=renewed.expires_at),
            )

        return self._handle(context, lambda: self._mutate(self._get_user_id(context), request.request_id, metadata_pb2.UpdateLeaseResponse, build))

    def UnlockBlocks(self, request: metadata_pb2.UnlockBlocksRequest, context: grpc.ServicerContext) -> metadata_pb2.UnlockBlocksResponse:  # noqa: N802
        def build() -> _Plan:
            file_id = self._get_lease_file_id(request.lease_id)
            key = self.keys.lease(file_id, request.lease_id)
            _, kv, _ = self.store.get(LeaseRecord, key)
            if kv is None:
                return _Plan([], [], metadata_pb2.UnlockBlocksResponse())  # ya liberado o caducado
            view = self._read_leases(file_id)
            # Lo reservado y no confirmado queda huérfano: lo borra la recolección de basura (§8.4)
            return _Plan(
                [compare_mod_revision(key, kv.mod_revision), compare_mod_revision(self.keys.lease_guard(file_id), view.guard_mod_revision)],
                [op_delete(key), op_delete_prefix(self.keys.pending_prefix(request.lease_id)), self._bump_lease_guard(file_id, view)],
                metadata_pb2.UnlockBlocksResponse(),
            )

        return self._handle(context, lambda: self._mutate(self._get_user_id(context), request.request_id, metadata_pb2.UnlockBlocksResponse, build))

    def AllocateBlocks(self, request: metadata_pb2.AllocateBlocksRequest, context: grpc.ServicerContext) -> metadata_pb2.AllocateBlocksResponse:  # noqa: N802
        def build() -> _Plan:
            user_id = self._get_user_id(context)
            handle = self._decode_handle(context, request.file_handle)
            self._require_write_handle(handle)
            lease, lease_key, lease_mod_revision = self._get_valid_lease(user_id, request.lease_id)
            if lease.file_id != handle.file_id:
                raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "El arrendamiento es de otro archivo")
            indices = list(request.block_indices)
            if not indices or len(indices) > MAX_BLOCKS_PER_ALLOCATION or len(set(indices)) != len(indices):
                raise DfshaError(
                    grpc.StatusCode.INVALID_ARGUMENT,
                    f"Hay que reservar entre 1 y {MAX_BLOCKS_PER_ALLOCATION} índices distintos",
                    Reason.BLOCK_RANGE_INVALID,
                )
            if not all(_range_contains(lease.block_range, index) for index in indices):
                raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "Hay índices fuera del rango arrendado", Reason.BLOCK_RANGE_INVALID)
            placements = self.registry.choose_nodes(len(indices), self.settings.replication_factor, handle.block_size_bytes)
            if not placements or len(placements[0]) < self.settings.write_quorum:
                raise DfshaError(
                    grpc.StatusCode.UNAVAILABLE,
                    f"Hay menos de {self.settings.write_quorum} nodos de datos vivos",
                    Reason.QUORUM_NOT_REACHED,
                )
            # Los tokens de escritura llegan en la etapa 6 (ADR 0022)
            blocks = [
                common_pb2.BlockLocation(block_index=index, block_id=str(uuid.uuid4()), datanode_addrs=addrs)
                for index, addrs in zip(indices, placements, strict=True)
            ]
            pending = PendingRecord(file_id=handle.file_id, blocks=blocks)
            return _Plan(
                [compare_mod_revision(lease_key, lease_mod_revision)],
                [op_put(self.keys.pending(request.lease_id, request.request_id), pending.SerializeToString())],
                metadata_pb2.AllocateBlocksResponse(blocks=blocks),
            )

        return self._handle(context, lambda: self._mutate(self._get_user_id(context), request.request_id, metadata_pb2.AllocateBlocksResponse, build))

    def CommitFile(self, request: metadata_pb2.CommitFileRequest, context: grpc.ServicerContext) -> metadata_pb2.CommitFileResponse:  # noqa: N802
        def build() -> _Plan:
            user_id = self._get_user_id(context)
            handle = self._decode_handle(context, request.file_handle)
            self._require_write_handle(handle)
            lease, lease_key, lease_mod_revision = self._get_valid_lease(user_id, request.lease_id)
            if lease.file_id != handle.file_id:
                raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "El arrendamiento es de otro archivo")
            committed = sorted(request.blocks, key=lambda block: block.block_index)
            self._verify_committed_blocks(request.lease_id, lease, committed)
            now = self._now()
            compares = [compare_mod_revision(lease_key, lease_mod_revision)]
            ops = [op_delete_prefix(self.keys.pending_prefix(request.lease_id))]
            if handle.mode == metadata_pb2.OPEN_MODE_CREATE:
                if request.write_mode != common_pb2.WRITE_MODE_CREATE:
                    raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "Un archivo abierto para crear se confirma en modo creación")
                self._require_full_range(lease)
                new_blocks = self._require_contiguous(committed)
                file_record = FileRecord(
                    file_id=handle.file_id, owner_user_id=user_id, block_size_bytes=handle.block_size_bytes
                )
                entry_key = self.keys.entry(user_id, handle.parent_directory_id, handle.name)
                entry = EntryRecord(type=metadata_pb2.ENTRY_TYPE_FILE, target_id=handle.file_id, modified_at=_now_timestamp(now))
                compares.append(compare_absent(entry_key))
                compares.append(compare_absent(self.keys.file(handle.file_id)))
                if handle.parent_entry_key:
                    compares.append(compare_create_revision(handle.parent_entry_key, handle.parent_create_revision))
                ops.append(op_put(entry_key, entry.SerializeToString()))
            else:
                current, file_kv, _ = self.store.get(FileRecord, self.keys.file(handle.file_id))
                if current is None or file_kv is None or current.is_deleted:
                    raise DfshaError(grpc.StatusCode.NOT_FOUND, "El archivo ya no existe", Reason.PATH_NOT_FOUND)
                file_record = current
                compares.append(compare_mod_revision(self.keys.file(handle.file_id), file_kv.mod_revision))
                new_blocks = self._build_new_blocks(handle, current, request.write_mode, lease, committed)
                ops.extend(self._supersede_version(current, now))
            new_version = file_record.current_version + 1
            updated = FileRecord()
            updated.CopyFrom(file_record)
            updated.current_version = new_version
            updated.current_size_bytes = request.size_bytes
            updated.modified_at.CopyFrom(_now_timestamp(now))
            version = VersionRecord(
                version=new_version, blocks=new_blocks, size_bytes=request.size_bytes, committed_at=_now_timestamp(now)
            )
            ops.append(op_put(self.keys.file(handle.file_id), updated.SerializeToString()))
            ops.append(op_put(self.keys.version(handle.file_id, new_version), version.SerializeToString()))
            return _Plan(compares, ops, metadata_pb2.CommitFileResponse(version=new_version))

        return self._handle(context, lambda: self._mutate(self._get_user_id(context), request.request_id, metadata_pb2.CommitFileResponse, build))

    def AbortFile(self, request: metadata_pb2.AbortFileRequest, context: grpc.ServicerContext) -> metadata_pb2.AbortFileResponse:  # noqa: N802
        def build() -> _Plan:
            user_id = self._get_user_id(context)
            handle = self._decode_handle(context, request.file_handle)
            lease, lease_key, lease_mod_revision = self._get_valid_lease(user_id, request.lease_id)
            if lease.file_id != handle.file_id:
                raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "El arrendamiento es de otro archivo")
            # Los bloques reservados quedan huérfanos y los borra la recolección de basura (§8.4)
            return _Plan(
                [compare_mod_revision(lease_key, lease_mod_revision)],
                [op_delete_prefix(self.keys.pending_prefix(request.lease_id))],
                metadata_pb2.AbortFileResponse(),
            )

        return self._handle(context, lambda: self._mutate(self._get_user_id(context), request.request_id, metadata_pb2.AbortFileResponse, build))

    # ===== Nodos de datos ======================================================================

    def RegisterDataNode(self, request: metadata_pb2.RegisterDataNodeRequest, context: grpc.ServicerContext) -> metadata_pb2.RegisterDataNodeResponse:  # noqa: N802
        def operation() -> metadata_pb2.RegisterDataNodeResponse:
            if not request.node_id or not request.hostname or not request.addr:
                raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "Faltan el node_id, el nombre de host o la dirección")
            try:
                parse_addr(request.addr)
            except ConfigError as error:
                raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, str(error)) from error
            record = NodeRecord(
                node_id=request.node_id,
                hostname=request.hostname,
                addr=request.addr,
                capacity_bytes=request.capacity_bytes,
                registered_at=_now_timestamp(self._now()),
            )
            if not self._apply_without_request([], [op_put(self.keys.node(request.node_id), record.SerializeToString())]):
                raise DfshaError(grpc.StatusCode.ABORTED, "No se pudo registrar el nodo; reintenta")
            self.registry.register(record, request.free_bytes)
            logger.info("Nodo de datos %s registrado en %s", request.node_id, record.addr)
            return metadata_pb2.RegisterDataNodeResponse(is_block_report_required=True)

        return self._handle(context, operation)

    def ReportHeartbeat(self, request: metadata_pb2.ReportHeartbeatRequest, context: grpc.ServicerContext) -> metadata_pb2.ReportHeartbeatResponse:  # noqa: N802
        def operation() -> metadata_pb2.ReportHeartbeatResponse:
            first_since_election = self.registry.get_state(request.node_id) is NodeState.WITHOUT_HEARTBEAT
            if not self.registry.record_heartbeat(request.node_id, request.free_bytes):
                raise DfshaError(grpc.StatusCode.FAILED_PRECONDITION, f"El nodo {request.node_id} no está registrado")
            commands = []
            if first_since_election:
                # Tras una elección, el líder pide el informe de bloques (Tabla 19)
                commands.append(metadata_pb2.DataNodeCommand(type=metadata_pb2.DATA_NODE_COMMAND_TYPE_SEND_BLOCK_REPORT))
            return metadata_pb2.ReportHeartbeatResponse(commands=commands, leader_epoch=self.election.epoch)

        return self._handle(context, operation)

    def ReportBlocks(self, request: metadata_pb2.ReportBlocksRequest, context: grpc.ServicerContext) -> metadata_pb2.ReportBlocksResponse:  # noqa: N802
        def operation() -> metadata_pb2.ReportBlocksResponse:
            now = _now_timestamp(self._now())
            ops = [self._put_replica(request.node_id, block, now) for block in request.blocks]
            for start in range(0, len(ops), _OPS_PER_TXN):
                self._apply_without_request([], ops[start : start + _OPS_PER_TXN])
            # Las órdenes de borrado y de re-replicación llegan en la etapa 9 (ADR 0018)
            return metadata_pb2.ReportBlocksResponse(leader_epoch=self.election.epoch)

        return self._handle(context, operation)

    def ReportBlockReceived(self, request: metadata_pb2.ReportBlockReceivedRequest, context: grpc.ServicerContext) -> metadata_pb2.ReportBlockReceivedResponse:  # noqa: N802
        def operation() -> metadata_pb2.ReportBlockReceivedResponse:
            if not request.node_id or not request.block.block_id or len(request.block.block_sha256) != 32:
                raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "Aviso de bloque recibido incompleto")
            ops = [self._put_replica(request.node_id, request.block, _now_timestamp(self._now()))]
            if not self._apply_without_request([], ops):
                raise DfshaError(grpc.StatusCode.ABORTED, "No se pudo anotar la réplica; reintenta")
            return metadata_pb2.ReportBlockReceivedResponse()

        return self._handle(context, operation)

    # ===== Ayudas ==============================================================================

    def _build_entry(self, name: str, entry: EntryRecord, file_record: FileRecord | None = None) -> metadata_pb2.DirectoryEntry:
        result = metadata_pb2.DirectoryEntry(name=name, type=entry.type, modified_at=entry.modified_at)
        if file_record is not None:
            result.size_bytes = file_record.current_size_bytes
            result.version = file_record.current_version
            result.modified_at.CopyFrom(file_record.modified_at)
        return result

    def _build_file_info(self, path: str, file_record: FileRecord) -> metadata_pb2.FileInfo:
        block_count = -(-file_record.current_size_bytes // file_record.block_size_bytes) if file_record.block_size_bytes else 0
        return metadata_pb2.FileInfo(
            file_id=file_record.file_id,
            path=path,
            size_bytes=file_record.current_size_bytes,
            version=file_record.current_version,
            block_size_bytes=file_record.block_size_bytes,
            block_count=block_count,
            modified_at=file_record.modified_at,
        )

    def _get_file_of(self, resolution: Resolution) -> FileRecord:
        if not resolution.is_file or resolution.entry is None:
            raise path_not_found(resolution.path)
        file_record, _, _ = self.store.get(FileRecord, self.keys.file(resolution.entry.target_id))
        if file_record is None or file_record.is_deleted:
            raise path_not_found(resolution.path)
        return file_record

    def _parent_exists(self, resolution: Resolution) -> list[Compare]:
        """El directorio que contiene la entrada sigue existiendo y no se ha movido."""
        if not resolution.parent_entry_key:
            return []  # la raíz siempre existe
        return [compare_create_revision(resolution.parent_entry_key, resolution.parent_create_revision)]

    def _decode_handle(self, context: grpc.ServicerContext, file_handle: bytes) -> FileHandle:
        try:
            handle = FileHandle.FromString(file_handle)
        except Exception:
            handle = FileHandle()
        if not handle.file_id or handle.user_id != self._get_user_id(context):
            raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "Descriptor de archivo no válido")
        return handle  # se firma y se verifica en la etapa 6

    @staticmethod
    def _require_write_handle(handle: FileHandle) -> None:
        if handle.mode not in (metadata_pb2.OPEN_MODE_WRITE, metadata_pb2.OPEN_MODE_CREATE):
            raise DfshaError(grpc.StatusCode.FAILED_PRECONDITION, "El archivo está abierto solo para leer")

    def _get_live_version(self, file_id: str, version_number: int) -> VersionRecord:
        version, _, _ = self.store.get(VersionRecord, self.keys.version(file_id, version_number))
        if version is None or (version.HasField("expires_at") and _timestamp_seconds(version.expires_at) <= self._now()):
            raise DfshaError(
                grpc.StatusCode.FAILED_PRECONDITION,
                "La versión abierta ya no existe; vuelve a abrir el archivo",
                Reason.FILE_VERSION_EXPIRED,
            )
        return version

    def _supersede_version(self, file_record: FileRecord, now: float) -> list[RequestOp]:
        """Marca la versión vigente como sustituida, legible durante el periodo de gracia (§7.3)."""
        if not file_record.current_version:
            return []
        key = self.keys.version(file_record.file_id, file_record.current_version)
        version, _, _ = self.store.get(VersionRecord, key)
        if version is None:
            return []
        version.expires_at.CopyFrom(_now_timestamp(now + self.settings.grace_period_s))
        return [op_put(key, version.SerializeToString())]

    def _put_replica(self, node_id: str, block: metadata_pb2.StoredBlock, now: Timestamp) -> RequestOp:
        replica = ReplicaRecord(
            node_id=node_id, block_sha256=block.block_sha256, size_bytes=block.size_bytes, reported_at=now
        )
        return op_put(self.keys.replica(block.block_id, node_id), replica.SerializeToString())

    # ----- Arrendamientos --------------------------------------------------------------------

    def _is_lease_alive(self, lease: LeaseRecord) -> bool:
        return _timestamp_seconds(lease.expires_at) > self._now()

    def _read_leases(self, file_id: str) -> _LeaseView:
        view = _LeaseView()
        guard_kv, revision = self.store.etcd.get(self.keys.lease_guard(file_id))
        if guard_kv is not None:
            view.guard_mod_revision = guard_kv.mod_revision
            view.guard_value = int(guard_kv.value or b"0")
        kvs, _ = self.store.etcd.get_prefix(self.keys.leases_prefix(file_id), revision=revision)
        view.leases = [(LeaseRecord.FromString(kv.value), kv.key) for kv in kvs]
        return view

    def _delete_expired_leases(self, view: _LeaseView) -> list[RequestOp]:
        ops = []
        for lease, key in view.leases:
            if not self._is_lease_alive(lease):
                ops.append(op_delete(key))
                ops.append(op_delete_prefix(self.keys.pending_prefix(lease.lease_id)))
        return ops[: _OPS_PER_TXN - 10]

    def _bump_lease_guard(self, file_id: str, view: _LeaseView) -> RequestOp:
        return op_put(self.keys.lease_guard(file_id), str(view.guard_value + 1).encode())

    @staticmethod
    def _get_lease_file_id(lease_id: str) -> str:
        file_id, separator, suffix = lease_id.rpartition(".")
        if not separator or not file_id or not suffix:
            raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "lease_id no válido")
        return file_id

    def _get_valid_lease(self, user_id: str, lease_id: str) -> tuple[LeaseRecord, bytes, int]:
        file_id = self._get_lease_file_id(lease_id)
        key = self.keys.lease(file_id, lease_id)
        lease, kv, _ = self.store.get(LeaseRecord, key)
        if lease is None or kv is None or not self._is_lease_alive(lease):
            raise DfshaError(grpc.StatusCode.ABORTED, "El arrendamiento caducó", Reason.LEASE_EXPIRED)
        if lease.user_id != user_id:
            raise DfshaError(grpc.StatusCode.PERMISSION_DENIED, "El arrendamiento es de otro usuario")
        return lease, key, kv.mod_revision

    # ----- Confirmación ----------------------------------------------------------------------

    def _verify_committed_blocks(self, lease_id: str, lease: LeaseRecord, committed: list[metadata_pb2.CommittedBlock]) -> None:
        """Cada bloque se reservó bajo este arrendamiento y tiene W avisos con su hash (§8.4)."""
        allocated: dict[int, set[str]] = {}
        kvs, _ = self.store.etcd.get_prefix(self.keys.pending_prefix(lease_id))
        for kv in kvs:
            for block in PendingRecord.FromString(kv.value).blocks:
                allocated.setdefault(block.block_index, set()).add(block.block_id)
        if len({block.block_index for block in committed}) != len(committed):
            raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "Hay índices de bloque repetidos", Reason.BLOCK_RANGE_INVALID)
        for block in committed:
            if not _range_contains(lease.block_range, block.block_index) or block.block_id not in allocated.get(block.block_index, set()):
                raise DfshaError(
                    grpc.StatusCode.INVALID_ARGUMENT,
                    f"El bloque {block.block_id} no se reservó para el índice {block.block_index}",
                    Reason.BLOCK_RANGE_INVALID,
                )
        replica_lists = self.store.get_prefixes([self.keys.replicas_prefix(block.block_id) for block in committed])
        for block, replica_kvs in zip(committed, replica_lists, strict=True):
            confirmed = [
                replica
                for replica in (ReplicaRecord.FromString(kv.value) for kv in replica_kvs)
                if not replica.is_corrupt and replica.block_sha256 == block.block_sha256 and replica.size_bytes == block.size_bytes
            ]
            if len(confirmed) < self.settings.write_quorum:
                raise DfshaError(
                    grpc.StatusCode.UNAVAILABLE,
                    f"El bloque {block.block_id} tiene {len(confirmed)} réplicas confirmadas; hacen falta {self.settings.write_quorum}",
                    Reason.QUORUM_NOT_REACHED,
                )

    @staticmethod
    def _require_full_range(lease: LeaseRecord) -> None:
        if lease.block_range.first_block_index != 0 or lease.block_range.block_count != 0:
            raise DfshaError(grpc.StatusCode.FAILED_PRECONDITION, "Crear o reemplazar exige arrendar el archivo entero")

    @staticmethod
    def _require_contiguous(blocks: list[metadata_pb2.CommittedBlock]) -> list[metadata_pb2.CommittedBlock]:
        if [block.block_index for block in blocks] != list(range(len(blocks))):
            raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "Los bloques tienen que ir del 0 al último sin huecos", Reason.BLOCK_RANGE_INVALID)
        return blocks

    def _build_new_blocks(
        self,
        handle: FileHandle,
        current: FileRecord,
        write_mode: common_pb2.WriteMode,
        lease: LeaseRecord,
        committed: list[metadata_pb2.CommittedBlock],
    ) -> list[metadata_pb2.CommittedBlock]:
        if write_mode == common_pb2.WRITE_MODE_REPLACE:
            self._require_full_range(lease)
            return self._require_contiguous(committed)
        if write_mode not in (common_pb2.WRITE_MODE_APPEND, common_pb2.WRITE_MODE_PARTIAL):
            raise DfshaError(grpc.StatusCode.INVALID_ARGUMENT, "Modo de escritura no válido para un archivo que existe")
        current_blocks = self._get_blocks(current.file_id, current.current_version)
        if handle.version != current.current_version:
            # Otro escritor confirmó después de abrir: solo vale si no tocó los índices que se sustituyen (§8.2)
            base_blocks = self._get_blocks(current.file_id, handle.version)
            for block in committed:
                if base_blocks.get(block.block_index) != current_blocks.get(block.block_index):
                    raise DfshaError(
                        grpc.StatusCode.ABORTED,
                        "Otro escritor cambió esos bloques después de abrir el archivo; vuelve a abrirlo",
                        Reason.VERSION_CONFLICT,
                    )
        merged = {index: block for index, block in current_blocks.items()}
        for block in committed:
            merged[block.block_index] = block
        return self._require_contiguous([merged[index] for index in sorted(merged)])

    def _get_blocks(self, file_id: str, version_number: int) -> dict[int, metadata_pb2.CommittedBlock]:
        if not version_number:
            return {}
        version, _, _ = self.store.get(VersionRecord, self.keys.version(file_id, version_number))
        if version is None:
            raise DfshaError(grpc.StatusCode.FAILED_PRECONDITION, "La versión base ya no existe", Reason.FILE_VERSION_EXPIRED)
        return {block.block_index: block for block in version.blocks}


__all__ = ["IMPLICIT_USER_ID", "MetadataService", "MetadataSettings", "ROOT_DIRECTORY_ID"]
