import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from dfsha.v1 import common_pb2 as _common_pb2
from dfsha.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class EntryRecord(_message.Message):
    __slots__ = ("type", "target_id", "modified_at")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    TARGET_ID_FIELD_NUMBER: _ClassVar[int]
    MODIFIED_AT_FIELD_NUMBER: _ClassVar[int]
    type: _metadata_pb2.EntryType
    target_id: str
    modified_at: _timestamp_pb2.Timestamp
    def __init__(self, type: _Optional[_Union[_metadata_pb2.EntryType, str]] = ..., target_id: _Optional[str] = ..., modified_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class FileRecord(_message.Message):
    __slots__ = ("file_id", "owner_user_id", "block_size_bytes", "current_version", "current_size_bytes", "modified_at", "wrapped_data_key", "is_deleted")
    FILE_ID_FIELD_NUMBER: _ClassVar[int]
    OWNER_USER_ID_FIELD_NUMBER: _ClassVar[int]
    BLOCK_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    CURRENT_VERSION_FIELD_NUMBER: _ClassVar[int]
    CURRENT_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    MODIFIED_AT_FIELD_NUMBER: _ClassVar[int]
    WRAPPED_DATA_KEY_FIELD_NUMBER: _ClassVar[int]
    IS_DELETED_FIELD_NUMBER: _ClassVar[int]
    file_id: str
    owner_user_id: str
    block_size_bytes: int
    current_version: int
    current_size_bytes: int
    modified_at: _timestamp_pb2.Timestamp
    wrapped_data_key: bytes
    is_deleted: bool
    def __init__(self, file_id: _Optional[str] = ..., owner_user_id: _Optional[str] = ..., block_size_bytes: _Optional[int] = ..., current_version: _Optional[int] = ..., current_size_bytes: _Optional[int] = ..., modified_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., wrapped_data_key: _Optional[bytes] = ..., is_deleted: _Optional[bool] = ...) -> None: ...

class VersionRecord(_message.Message):
    __slots__ = ("version", "blocks", "size_bytes", "committed_at", "expires_at")
    VERSION_FIELD_NUMBER: _ClassVar[int]
    BLOCKS_FIELD_NUMBER: _ClassVar[int]
    SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    COMMITTED_AT_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    version: int
    blocks: _containers.RepeatedCompositeFieldContainer[_metadata_pb2.CommittedBlock]
    size_bytes: int
    committed_at: _timestamp_pb2.Timestamp
    expires_at: _timestamp_pb2.Timestamp
    def __init__(self, version: _Optional[int] = ..., blocks: _Optional[_Iterable[_Union[_metadata_pb2.CommittedBlock, _Mapping]]] = ..., size_bytes: _Optional[int] = ..., committed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ReplicaRecord(_message.Message):
    __slots__ = ("node_id", "block_sha256", "size_bytes", "reported_at", "is_corrupt")
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    BLOCK_SHA256_FIELD_NUMBER: _ClassVar[int]
    SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    REPORTED_AT_FIELD_NUMBER: _ClassVar[int]
    IS_CORRUPT_FIELD_NUMBER: _ClassVar[int]
    node_id: str
    block_sha256: bytes
    size_bytes: int
    reported_at: _timestamp_pb2.Timestamp
    is_corrupt: bool
    def __init__(self, node_id: _Optional[str] = ..., block_sha256: _Optional[bytes] = ..., size_bytes: _Optional[int] = ..., reported_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., is_corrupt: _Optional[bool] = ...) -> None: ...

class PendingRecord(_message.Message):
    __slots__ = ("file_id", "blocks")
    FILE_ID_FIELD_NUMBER: _ClassVar[int]
    BLOCKS_FIELD_NUMBER: _ClassVar[int]
    file_id: str
    blocks: _containers.RepeatedCompositeFieldContainer[_common_pb2.BlockLocation]
    def __init__(self, file_id: _Optional[str] = ..., blocks: _Optional[_Iterable[_Union[_common_pb2.BlockLocation, _Mapping]]] = ...) -> None: ...

class LeaseRecord(_message.Message):
    __slots__ = ("lease_id", "file_id", "user_id", "block_range", "expires_at")
    LEASE_ID_FIELD_NUMBER: _ClassVar[int]
    FILE_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    BLOCK_RANGE_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    lease_id: str
    file_id: str
    user_id: str
    block_range: _common_pb2.BlockRange
    expires_at: _timestamp_pb2.Timestamp
    def __init__(self, lease_id: _Optional[str] = ..., file_id: _Optional[str] = ..., user_id: _Optional[str] = ..., block_range: _Optional[_Union[_common_pb2.BlockRange, _Mapping]] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class NodeRecord(_message.Message):
    __slots__ = ("node_id", "hostname", "addr", "capacity_bytes", "registered_at")
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    HOSTNAME_FIELD_NUMBER: _ClassVar[int]
    ADDR_FIELD_NUMBER: _ClassVar[int]
    CAPACITY_BYTES_FIELD_NUMBER: _ClassVar[int]
    REGISTERED_AT_FIELD_NUMBER: _ClassVar[int]
    node_id: str
    hostname: str
    addr: str
    capacity_bytes: int
    registered_at: _timestamp_pb2.Timestamp
    def __init__(self, node_id: _Optional[str] = ..., hostname: _Optional[str] = ..., addr: _Optional[str] = ..., capacity_bytes: _Optional[int] = ..., registered_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class FileHandle(_message.Message):
    __slots__ = ("file_id", "version", "mode", "user_id", "block_size_bytes", "parent_directory_id", "name", "parent_entry_key", "parent_create_revision")
    FILE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    BLOCK_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    PARENT_DIRECTORY_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    PARENT_ENTRY_KEY_FIELD_NUMBER: _ClassVar[int]
    PARENT_CREATE_REVISION_FIELD_NUMBER: _ClassVar[int]
    file_id: str
    version: int
    mode: _metadata_pb2.OpenMode
    user_id: str
    block_size_bytes: int
    parent_directory_id: str
    name: str
    parent_entry_key: bytes
    parent_create_revision: int
    def __init__(self, file_id: _Optional[str] = ..., version: _Optional[int] = ..., mode: _Optional[_Union[_metadata_pb2.OpenMode, str]] = ..., user_id: _Optional[str] = ..., block_size_bytes: _Optional[int] = ..., parent_directory_id: _Optional[str] = ..., name: _Optional[str] = ..., parent_entry_key: _Optional[bytes] = ..., parent_create_revision: _Optional[int] = ...) -> None: ...
