import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from dfsha.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class EntryType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ENTRY_TYPE_UNSPECIFIED: _ClassVar[EntryType]
    ENTRY_TYPE_FILE: _ClassVar[EntryType]
    ENTRY_TYPE_DIRECTORY: _ClassVar[EntryType]

class OpenMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    OPEN_MODE_UNSPECIFIED: _ClassVar[OpenMode]
    OPEN_MODE_READ: _ClassVar[OpenMode]
    OPEN_MODE_WRITE: _ClassVar[OpenMode]
    OPEN_MODE_CREATE: _ClassVar[OpenMode]

class DataNodeCommandType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DATA_NODE_COMMAND_TYPE_UNSPECIFIED: _ClassVar[DataNodeCommandType]
    DATA_NODE_COMMAND_TYPE_REPLICATE: _ClassVar[DataNodeCommandType]
    DATA_NODE_COMMAND_TYPE_DELETE: _ClassVar[DataNodeCommandType]
    DATA_NODE_COMMAND_TYPE_VERIFY: _ClassVar[DataNodeCommandType]
    DATA_NODE_COMMAND_TYPE_SEND_BLOCK_REPORT: _ClassVar[DataNodeCommandType]
ENTRY_TYPE_UNSPECIFIED: EntryType
ENTRY_TYPE_FILE: EntryType
ENTRY_TYPE_DIRECTORY: EntryType
OPEN_MODE_UNSPECIFIED: OpenMode
OPEN_MODE_READ: OpenMode
OPEN_MODE_WRITE: OpenMode
OPEN_MODE_CREATE: OpenMode
DATA_NODE_COMMAND_TYPE_UNSPECIFIED: DataNodeCommandType
DATA_NODE_COMMAND_TYPE_REPLICATE: DataNodeCommandType
DATA_NODE_COMMAND_TYPE_DELETE: DataNodeCommandType
DATA_NODE_COMMAND_TYPE_VERIFY: DataNodeCommandType
DATA_NODE_COMMAND_TYPE_SEND_BLOCK_REPORT: DataNodeCommandType

class FileInfo(_message.Message):
    __slots__ = ("file_id", "path", "size_bytes", "version", "block_size_bytes", "block_count", "modified_at")
    FILE_ID_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    BLOCK_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    BLOCK_COUNT_FIELD_NUMBER: _ClassVar[int]
    MODIFIED_AT_FIELD_NUMBER: _ClassVar[int]
    file_id: str
    path: str
    size_bytes: int
    version: int
    block_size_bytes: int
    block_count: int
    modified_at: _timestamp_pb2.Timestamp
    def __init__(self, file_id: _Optional[str] = ..., path: _Optional[str] = ..., size_bytes: _Optional[int] = ..., version: _Optional[int] = ..., block_size_bytes: _Optional[int] = ..., block_count: _Optional[int] = ..., modified_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class DirectoryEntry(_message.Message):
    __slots__ = ("name", "type", "size_bytes", "version", "modified_at")
    NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    MODIFIED_AT_FIELD_NUMBER: _ClassVar[int]
    name: str
    type: EntryType
    size_bytes: int
    version: int
    modified_at: _timestamp_pb2.Timestamp
    def __init__(self, name: _Optional[str] = ..., type: _Optional[_Union[EntryType, str]] = ..., size_bytes: _Optional[int] = ..., version: _Optional[int] = ..., modified_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class CommittedBlock(_message.Message):
    __slots__ = ("block_index", "block_id", "block_sha256", "size_bytes")
    BLOCK_INDEX_FIELD_NUMBER: _ClassVar[int]
    BLOCK_ID_FIELD_NUMBER: _ClassVar[int]
    BLOCK_SHA256_FIELD_NUMBER: _ClassVar[int]
    SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    block_index: int
    block_id: str
    block_sha256: bytes
    size_bytes: int
    def __init__(self, block_index: _Optional[int] = ..., block_id: _Optional[str] = ..., block_sha256: _Optional[bytes] = ..., size_bytes: _Optional[int] = ...) -> None: ...

class StoredBlock(_message.Message):
    __slots__ = ("block_id", "block_sha256", "size_bytes")
    BLOCK_ID_FIELD_NUMBER: _ClassVar[int]
    BLOCK_SHA256_FIELD_NUMBER: _ClassVar[int]
    SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    block_id: str
    block_sha256: bytes
    size_bytes: int
    def __init__(self, block_id: _Optional[str] = ..., block_sha256: _Optional[bytes] = ..., size_bytes: _Optional[int] = ...) -> None: ...

class DataNodeCommand(_message.Message):
    __slots__ = ("type", "block_id", "target_addr", "target_block_token")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    BLOCK_ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_ADDR_FIELD_NUMBER: _ClassVar[int]
    TARGET_BLOCK_TOKEN_FIELD_NUMBER: _ClassVar[int]
    type: DataNodeCommandType
    block_id: str
    target_addr: str
    target_block_token: _common_pb2.BlockToken
    def __init__(self, type: _Optional[_Union[DataNodeCommandType, str]] = ..., block_id: _Optional[str] = ..., target_addr: _Optional[str] = ..., target_block_token: _Optional[_Union[_common_pb2.BlockToken, _Mapping]] = ...) -> None: ...

class AuthenticateRequest(_message.Message):
    __slots__ = ("username", "password")
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    username: str
    password: str
    def __init__(self, username: _Optional[str] = ..., password: _Optional[str] = ...) -> None: ...

class AuthenticateResponse(_message.Message):
    __slots__ = ("access_token", "expires_at")
    ACCESS_TOKEN_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    access_token: str
    expires_at: _timestamp_pb2.Timestamp
    def __init__(self, access_token: _Optional[str] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class CreateUserRequest(_message.Message):
    __slots__ = ("request_id", "username", "password", "is_admin")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    IS_ADMIN_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    username: str
    password: str
    is_admin: bool
    def __init__(self, request_id: _Optional[str] = ..., username: _Optional[str] = ..., password: _Optional[str] = ..., is_admin: _Optional[bool] = ...) -> None: ...

class CreateUserResponse(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    def __init__(self, user_id: _Optional[str] = ...) -> None: ...

class ListDirectoryRequest(_message.Message):
    __slots__ = ("path",)
    PATH_FIELD_NUMBER: _ClassVar[int]
    path: str
    def __init__(self, path: _Optional[str] = ...) -> None: ...

class ListDirectoryResponse(_message.Message):
    __slots__ = ("entries",)
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    entries: _containers.RepeatedCompositeFieldContainer[DirectoryEntry]
    def __init__(self, entries: _Optional[_Iterable[_Union[DirectoryEntry, _Mapping]]] = ...) -> None: ...

class GetFileInfoRequest(_message.Message):
    __slots__ = ("path",)
    PATH_FIELD_NUMBER: _ClassVar[int]
    path: str
    def __init__(self, path: _Optional[str] = ...) -> None: ...

class GetFileInfoResponse(_message.Message):
    __slots__ = ("info",)
    INFO_FIELD_NUMBER: _ClassVar[int]
    info: FileInfo
    def __init__(self, info: _Optional[_Union[FileInfo, _Mapping]] = ...) -> None: ...

class CreateDirectoryRequest(_message.Message):
    __slots__ = ("request_id", "path")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    path: str
    def __init__(self, request_id: _Optional[str] = ..., path: _Optional[str] = ...) -> None: ...

class CreateDirectoryResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class DeleteDirectoryRequest(_message.Message):
    __slots__ = ("request_id", "path")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    path: str
    def __init__(self, request_id: _Optional[str] = ..., path: _Optional[str] = ...) -> None: ...

class DeleteDirectoryResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class DeleteFileRequest(_message.Message):
    __slots__ = ("request_id", "path")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    path: str
    def __init__(self, request_id: _Optional[str] = ..., path: _Optional[str] = ...) -> None: ...

class DeleteFileResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class MovePathRequest(_message.Message):
    __slots__ = ("request_id", "source_path", "target_path")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    SOURCE_PATH_FIELD_NUMBER: _ClassVar[int]
    TARGET_PATH_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    source_path: str
    target_path: str
    def __init__(self, request_id: _Optional[str] = ..., source_path: _Optional[str] = ..., target_path: _Optional[str] = ...) -> None: ...

class MovePathResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class OpenFileRequest(_message.Message):
    __slots__ = ("path", "mode")
    PATH_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    path: str
    mode: OpenMode
    def __init__(self, path: _Optional[str] = ..., mode: _Optional[_Union[OpenMode, str]] = ...) -> None: ...

class OpenFileResponse(_message.Message):
    __slots__ = ("file_handle", "info", "data_key")
    FILE_HANDLE_FIELD_NUMBER: _ClassVar[int]
    INFO_FIELD_NUMBER: _ClassVar[int]
    DATA_KEY_FIELD_NUMBER: _ClassVar[int]
    file_handle: bytes
    info: FileInfo
    data_key: bytes
    def __init__(self, file_handle: _Optional[bytes] = ..., info: _Optional[_Union[FileInfo, _Mapping]] = ..., data_key: _Optional[bytes] = ...) -> None: ...

class GetBlockLocationsRequest(_message.Message):
    __slots__ = ("file_handle", "block_range")
    FILE_HANDLE_FIELD_NUMBER: _ClassVar[int]
    BLOCK_RANGE_FIELD_NUMBER: _ClassVar[int]
    file_handle: bytes
    block_range: _common_pb2.BlockRange
    def __init__(self, file_handle: _Optional[bytes] = ..., block_range: _Optional[_Union[_common_pb2.BlockRange, _Mapping]] = ...) -> None: ...

class GetBlockLocationsResponse(_message.Message):
    __slots__ = ("locations",)
    LOCATIONS_FIELD_NUMBER: _ClassVar[int]
    locations: _containers.RepeatedCompositeFieldContainer[_common_pb2.BlockLocation]
    def __init__(self, locations: _Optional[_Iterable[_Union[_common_pb2.BlockLocation, _Mapping]]] = ...) -> None: ...

class LockBlocksRequest(_message.Message):
    __slots__ = ("request_id", "file_handle", "block_range")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    FILE_HANDLE_FIELD_NUMBER: _ClassVar[int]
    BLOCK_RANGE_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    file_handle: bytes
    block_range: _common_pb2.BlockRange
    def __init__(self, request_id: _Optional[str] = ..., file_handle: _Optional[bytes] = ..., block_range: _Optional[_Union[_common_pb2.BlockRange, _Mapping]] = ...) -> None: ...

class LockBlocksResponse(_message.Message):
    __slots__ = ("lease_id", "expires_at", "current_version")
    LEASE_ID_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    CURRENT_VERSION_FIELD_NUMBER: _ClassVar[int]
    lease_id: str
    expires_at: _timestamp_pb2.Timestamp
    current_version: int
    def __init__(self, lease_id: _Optional[str] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., current_version: _Optional[int] = ...) -> None: ...

class UpdateLeaseRequest(_message.Message):
    __slots__ = ("request_id", "lease_id")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    LEASE_ID_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    lease_id: str
    def __init__(self, request_id: _Optional[str] = ..., lease_id: _Optional[str] = ...) -> None: ...

class UpdateLeaseResponse(_message.Message):
    __slots__ = ("expires_at",)
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    expires_at: _timestamp_pb2.Timestamp
    def __init__(self, expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class UnlockBlocksRequest(_message.Message):
    __slots__ = ("request_id", "lease_id")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    LEASE_ID_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    lease_id: str
    def __init__(self, request_id: _Optional[str] = ..., lease_id: _Optional[str] = ...) -> None: ...

class UnlockBlocksResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class AllocateBlocksRequest(_message.Message):
    __slots__ = ("request_id", "file_handle", "lease_id", "block_indices")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    FILE_HANDLE_FIELD_NUMBER: _ClassVar[int]
    LEASE_ID_FIELD_NUMBER: _ClassVar[int]
    BLOCK_INDICES_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    file_handle: bytes
    lease_id: str
    block_indices: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, request_id: _Optional[str] = ..., file_handle: _Optional[bytes] = ..., lease_id: _Optional[str] = ..., block_indices: _Optional[_Iterable[int]] = ...) -> None: ...

class AllocateBlocksResponse(_message.Message):
    __slots__ = ("blocks",)
    BLOCKS_FIELD_NUMBER: _ClassVar[int]
    blocks: _containers.RepeatedCompositeFieldContainer[_common_pb2.BlockLocation]
    def __init__(self, blocks: _Optional[_Iterable[_Union[_common_pb2.BlockLocation, _Mapping]]] = ...) -> None: ...

class CommitFileRequest(_message.Message):
    __slots__ = ("request_id", "file_handle", "lease_id", "write_mode", "blocks", "size_bytes")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    FILE_HANDLE_FIELD_NUMBER: _ClassVar[int]
    LEASE_ID_FIELD_NUMBER: _ClassVar[int]
    WRITE_MODE_FIELD_NUMBER: _ClassVar[int]
    BLOCKS_FIELD_NUMBER: _ClassVar[int]
    SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    file_handle: bytes
    lease_id: str
    write_mode: _common_pb2.WriteMode
    blocks: _containers.RepeatedCompositeFieldContainer[CommittedBlock]
    size_bytes: int
    def __init__(self, request_id: _Optional[str] = ..., file_handle: _Optional[bytes] = ..., lease_id: _Optional[str] = ..., write_mode: _Optional[_Union[_common_pb2.WriteMode, str]] = ..., blocks: _Optional[_Iterable[_Union[CommittedBlock, _Mapping]]] = ..., size_bytes: _Optional[int] = ...) -> None: ...

class CommitFileResponse(_message.Message):
    __slots__ = ("version",)
    VERSION_FIELD_NUMBER: _ClassVar[int]
    version: int
    def __init__(self, version: _Optional[int] = ...) -> None: ...

class AbortFileRequest(_message.Message):
    __slots__ = ("request_id", "file_handle", "lease_id")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    FILE_HANDLE_FIELD_NUMBER: _ClassVar[int]
    LEASE_ID_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    file_handle: bytes
    lease_id: str
    def __init__(self, request_id: _Optional[str] = ..., file_handle: _Optional[bytes] = ..., lease_id: _Optional[str] = ...) -> None: ...

class AbortFileResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RegisterDataNodeRequest(_message.Message):
    __slots__ = ("node_id", "hostname", "capacity_bytes", "free_bytes")
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    HOSTNAME_FIELD_NUMBER: _ClassVar[int]
    CAPACITY_BYTES_FIELD_NUMBER: _ClassVar[int]
    FREE_BYTES_FIELD_NUMBER: _ClassVar[int]
    node_id: str
    hostname: str
    capacity_bytes: int
    free_bytes: int
    def __init__(self, node_id: _Optional[str] = ..., hostname: _Optional[str] = ..., capacity_bytes: _Optional[int] = ..., free_bytes: _Optional[int] = ...) -> None: ...

class RegisterDataNodeResponse(_message.Message):
    __slots__ = ("is_block_report_required",)
    IS_BLOCK_REPORT_REQUIRED_FIELD_NUMBER: _ClassVar[int]
    is_block_report_required: bool
    def __init__(self, is_block_report_required: _Optional[bool] = ...) -> None: ...

class ReportHeartbeatRequest(_message.Message):
    __slots__ = ("node_id", "free_bytes", "used_bytes", "active_transfers")
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    FREE_BYTES_FIELD_NUMBER: _ClassVar[int]
    USED_BYTES_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_TRANSFERS_FIELD_NUMBER: _ClassVar[int]
    node_id: str
    free_bytes: int
    used_bytes: int
    active_transfers: int
    def __init__(self, node_id: _Optional[str] = ..., free_bytes: _Optional[int] = ..., used_bytes: _Optional[int] = ..., active_transfers: _Optional[int] = ...) -> None: ...

class ReportHeartbeatResponse(_message.Message):
    __slots__ = ("commands",)
    COMMANDS_FIELD_NUMBER: _ClassVar[int]
    commands: _containers.RepeatedCompositeFieldContainer[DataNodeCommand]
    def __init__(self, commands: _Optional[_Iterable[_Union[DataNodeCommand, _Mapping]]] = ...) -> None: ...

class ReportBlocksRequest(_message.Message):
    __slots__ = ("node_id", "blocks")
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    BLOCKS_FIELD_NUMBER: _ClassVar[int]
    node_id: str
    blocks: _containers.RepeatedCompositeFieldContainer[StoredBlock]
    def __init__(self, node_id: _Optional[str] = ..., blocks: _Optional[_Iterable[_Union[StoredBlock, _Mapping]]] = ...) -> None: ...

class ReportBlocksResponse(_message.Message):
    __slots__ = ("commands",)
    COMMANDS_FIELD_NUMBER: _ClassVar[int]
    commands: _containers.RepeatedCompositeFieldContainer[DataNodeCommand]
    def __init__(self, commands: _Optional[_Iterable[_Union[DataNodeCommand, _Mapping]]] = ...) -> None: ...

class ReportBlockReceivedRequest(_message.Message):
    __slots__ = ("node_id", "block")
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    BLOCK_FIELD_NUMBER: _ClassVar[int]
    node_id: str
    block: StoredBlock
    def __init__(self, node_id: _Optional[str] = ..., block: _Optional[_Union[StoredBlock, _Mapping]] = ...) -> None: ...

class ReportBlockReceivedResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ReportCorruptReplicaRequest(_message.Message):
    __slots__ = ("block_id", "node_id")
    BLOCK_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    block_id: str
    node_id: str
    def __init__(self, block_id: _Optional[str] = ..., node_id: _Optional[str] = ...) -> None: ...

class ReportCorruptReplicaResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
