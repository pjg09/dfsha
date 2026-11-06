"""Almacén de bloques: marca del volumen, área temporal, verificación y renombrado atómico."""

import hashlib
import os
import uuid
from pathlib import Path

import grpc
import pytest

from dfsha.common.errors import DfshaError, Reason
from dfsha.datanode.block_store import (
    NODE_ID_MARKER,
    BlockStore,
    DataDirectoryError,
    initialize_data_directory,
    validate_block_id,
    verify_data_directory,
)


@pytest.fixture
def store(tmp_path: Path) -> BlockStore:
    initialize_data_directory(tmp_path, "datanode-1")
    return BlockStore(tmp_path)


def _write(store: BlockStore, data: bytes, sha256: bytes | None = None) -> str:
    block_id = str(uuid.uuid4())
    staging = store.create_staging(block_id, sha256 or hashlib.sha256(data).digest(), len(data))
    staging.append(data)
    meta = staging.finish()
    store.commit(staging, meta)
    return block_id


def test_marker_is_required(tmp_path: Path) -> None:
    with pytest.raises(DataDirectoryError, match=NODE_ID_MARKER):
        verify_data_directory(tmp_path, "datanode-1", require_mount_point=False)


def test_marker_must_match_node_id(tmp_path: Path) -> None:
    initialize_data_directory(tmp_path, "datanode-1")
    verify_data_directory(tmp_path, "datanode-1", require_mount_point=False)
    with pytest.raises(DataDirectoryError, match="datanode-1"):
        verify_data_directory(tmp_path, "datanode-2", require_mount_point=False)


def test_mount_point_is_required(tmp_path: Path) -> None:
    initialize_data_directory(tmp_path, "datanode-1")
    with pytest.raises(DataDirectoryError, match="punto de montaje"):
        verify_data_directory(tmp_path, "datanode-1", require_mount_point=True)


def test_initialize_refuses_non_empty_directory(tmp_path: Path) -> None:
    (tmp_path / "otra-cosa").write_text("x")
    with pytest.raises(DataDirectoryError, match="no está vacío"):
        initialize_data_directory(tmp_path, "datanode-1")


@pytest.mark.parametrize("block_id", ["../../etc/passwd", "abc", str(uuid.uuid4()).upper(), ""])
def test_rejects_invalid_block_ids(block_id: str) -> None:
    with pytest.raises(DfshaError) as raised:
        validate_block_id(block_id)
    assert raised.value.code is grpc.StatusCode.INVALID_ARGUMENT


def test_write_and_get(store: BlockStore) -> None:
    data = os.urandom(3 * 1024 * 1024 + 7)
    block_id = _write(store, data)
    path, meta = store.get_block(block_id)
    assert path.read_bytes() == data
    assert meta.sha256 == hashlib.sha256(data).digest()
    assert meta.size_bytes == len(data)
    assert not any((store.data_directory / "staging").iterdir())


def test_wrong_hash_is_not_stored(store: BlockStore) -> None:
    block_id = str(uuid.uuid4())
    staging = store.create_staging(block_id, bytes(32), 4)
    staging.append(b"abcd")
    with pytest.raises(DfshaError) as raised:
        staging.finish()
    assert raised.value.reason is Reason.BLOCK_CORRUPTED
    store.discard(staging)
    with pytest.raises(DfshaError) as missing:
        store.get_block(block_id)
    assert missing.value.code is grpc.StatusCode.NOT_FOUND
    assert not any((store.data_directory / "staging").iterdir())


def test_more_bytes_than_announced(store: BlockStore) -> None:
    staging = store.create_staging(str(uuid.uuid4()), bytes(32), 3)
    with pytest.raises(DfshaError) as raised:
        staging.append(b"abcd")
    assert raised.value.reason is Reason.BLOCK_CORRUPTED
    store.discard(staging)


def test_retry_of_same_block_is_idempotent(store: BlockStore) -> None:
    data = b"bloque inmutable"
    block_id = str(uuid.uuid4())
    for expected in (True, False):
        staging = store.create_staging(block_id, hashlib.sha256(data).digest(), len(data))
        staging.append(data)
        assert store.commit(staging, staging.finish()) is expected
    assert store.get_block(block_id)[0].read_bytes() == data


def test_clean_staging_area(store: BlockStore) -> None:
    (store.data_directory / "staging" / "restos-de-un-bloque").write_bytes(b"x" * 10)
    assert store.clean_staging_area() == 1
    assert not any((store.data_directory / "staging").iterdir())
