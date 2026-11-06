import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class BlockOperation(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BLOCK_OPERATION_UNSPECIFIED: _ClassVar[BlockOperation]
    BLOCK_OPERATION_READ: _ClassVar[BlockOperation]
    BLOCK_OPERATION_WRITE: _ClassVar[BlockOperation]

class WriteMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    WRITE_MODE_UNSPECIFIED: _ClassVar[WriteMode]
    WRITE_MODE_CREATE: _ClassVar[WriteMode]
    WRITE_MODE_REPLACE: _ClassVar[WriteMode]
    WRITE_MODE_APPEND: _ClassVar[WriteMode]
    WRITE_MODE_PARTIAL: _ClassVar[WriteMode]
BLOCK_OPERATION_UNSPECIFIED: BlockOperation
BLOCK_OPERATION_READ: BlockOperation
BLOCK_OPERATION_WRITE: BlockOperation
WRITE_MODE_UNSPECIFIED: WriteMode
WRITE_MODE_CREATE: WriteMode
WRITE_MODE_REPLACE: WriteMode
WRITE_MODE_APPEND: WriteMode
WRITE_MODE_PARTIAL: WriteMode

class BlockToken(_message.Message):
    __slots__ = ("block_id", "operation", "expires_at", "signature")
    BLOCK_ID_FIELD_NUMBER: _ClassVar[int]
    OPERATION_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    SIGNATURE_FIELD_NUMBER: _ClassVar[int]
    block_id: str
    operation: BlockOperation
    expires_at: _timestamp_pb2.Timestamp
    signature: bytes
    def __init__(self, block_id: _Optional[str] = ..., operation: _Optional[_Union[BlockOperation, str]] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., signature: _Optional[bytes] = ...) -> None: ...

class BlockRange(_message.Message):
    __slots__ = ("first_block_index", "block_count")
    FIRST_BLOCK_INDEX_FIELD_NUMBER: _ClassVar[int]
    BLOCK_COUNT_FIELD_NUMBER: _ClassVar[int]
    first_block_index: int
    block_count: int
    def __init__(self, first_block_index: _Optional[int] = ..., block_count: _Optional[int] = ...) -> None: ...

class BlockLocation(_message.Message):
    __slots__ = ("block_index", "block_id", "block_sha256", "size_bytes", "datanode_addrs", "block_token")
    BLOCK_INDEX_FIELD_NUMBER: _ClassVar[int]
    BLOCK_ID_FIELD_NUMBER: _ClassVar[int]
    BLOCK_SHA256_FIELD_NUMBER: _ClassVar[int]
    SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    DATANODE_ADDRS_FIELD_NUMBER: _ClassVar[int]
    BLOCK_TOKEN_FIELD_NUMBER: _ClassVar[int]
    block_index: int
    block_id: str
    block_sha256: bytes
    size_bytes: int
    datanode_addrs: _containers.RepeatedScalarFieldContainer[str]
    block_token: BlockToken
    def __init__(self, block_index: _Optional[int] = ..., block_id: _Optional[str] = ..., block_sha256: _Optional[bytes] = ..., size_bytes: _Optional[int] = ..., datanode_addrs: _Optional[_Iterable[str]] = ..., block_token: _Optional[_Union[BlockToken, _Mapping]] = ...) -> None: ...
