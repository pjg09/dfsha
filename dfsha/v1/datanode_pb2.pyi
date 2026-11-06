from dfsha.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class WriteBlockHeader(_message.Message):
    __slots__ = ("block_id", "block_token", "block_sha256", "size_bytes", "secondary_addrs")
    BLOCK_ID_FIELD_NUMBER: _ClassVar[int]
    BLOCK_TOKEN_FIELD_NUMBER: _ClassVar[int]
    BLOCK_SHA256_FIELD_NUMBER: _ClassVar[int]
    SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    SECONDARY_ADDRS_FIELD_NUMBER: _ClassVar[int]
    block_id: str
    block_token: _common_pb2.BlockToken
    block_sha256: bytes
    size_bytes: int
    secondary_addrs: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, block_id: _Optional[str] = ..., block_token: _Optional[_Union[_common_pb2.BlockToken, _Mapping]] = ..., block_sha256: _Optional[bytes] = ..., size_bytes: _Optional[int] = ..., secondary_addrs: _Optional[_Iterable[str]] = ...) -> None: ...

class WriteBlockRequest(_message.Message):
    __slots__ = ("header", "data")
    HEADER_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    header: WriteBlockHeader
    data: bytes
    def __init__(self, header: _Optional[_Union[WriteBlockHeader, _Mapping]] = ..., data: _Optional[bytes] = ...) -> None: ...

class WriteBlockResponse(_message.Message):
    __slots__ = ("stored_on",)
    STORED_ON_FIELD_NUMBER: _ClassVar[int]
    stored_on: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, stored_on: _Optional[_Iterable[str]] = ...) -> None: ...

class ReadBlockRequest(_message.Message):
    __slots__ = ("block_id", "block_token")
    BLOCK_ID_FIELD_NUMBER: _ClassVar[int]
    BLOCK_TOKEN_FIELD_NUMBER: _ClassVar[int]
    block_id: str
    block_token: _common_pb2.BlockToken
    def __init__(self, block_id: _Optional[str] = ..., block_token: _Optional[_Union[_common_pb2.BlockToken, _Mapping]] = ...) -> None: ...

class ReadBlockHeader(_message.Message):
    __slots__ = ("size_bytes", "block_sha256")
    SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    BLOCK_SHA256_FIELD_NUMBER: _ClassVar[int]
    size_bytes: int
    block_sha256: bytes
    def __init__(self, size_bytes: _Optional[int] = ..., block_sha256: _Optional[bytes] = ...) -> None: ...

class ReadBlockResponse(_message.Message):
    __slots__ = ("header", "data")
    HEADER_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    header: ReadBlockHeader
    data: bytes
    def __init__(self, header: _Optional[_Union[ReadBlockHeader, _Mapping]] = ..., data: _Optional[bytes] = ...) -> None: ...
