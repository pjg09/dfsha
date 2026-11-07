"""Primitivas de seguridad: firmas, tokens, contraseñas y cifrado de sobre."""

import time
import uuid

import pytest

from dfsha.common import security
from dfsha.common.security import InvalidSignatureError
from dfsha.v1 import common_pb2

KEY = b"k" * 32
OTHER_KEY = b"o" * 32


def test_access_token_round_trip_and_tampering() -> None:
    token, expires_at = security.create_access_token(KEY, "user-1", is_admin=False)
    claims = security.verify_access_token(KEY, token)
    assert (claims.user_id, claims.is_admin) == ("user-1", False)
    assert not security.is_expired(expires_at)
    with pytest.raises(InvalidSignatureError):
        security.verify_access_token(OTHER_KEY, token)
    payload, mac = token.split(".")
    forged = security._b64encode(security.AccessTokenClaims(user_id="otro", is_admin=True).SerializeToString()) + "." + mac
    with pytest.raises(InvalidSignatureError):
        security.verify_access_token(KEY, forged)
    with pytest.raises(InvalidSignatureError):
        security.verify_access_token(KEY, "basura")


def test_expiry_allows_clock_skew_margin() -> None:
    _, expires_at = security.create_access_token(KEY, "u", False, now=time.time() - security.ACCESS_TOKEN_TTL_S - 10)
    assert not security.is_expired(expires_at)  # caducó hace 10 s: dentro del margen de 30 s
    _, old = security.create_access_token(KEY, "u", False, now=time.time() - security.ACCESS_TOKEN_TTL_S - 40)
    assert security.is_expired(old)


def test_domains_are_separated() -> None:
    # Una firma de descriptor de archivo no vale como token de acceso aunque la clave sea la misma
    payload = security.AccessTokenClaims(user_id="u", is_admin=True).SerializeToString()
    handle = security.sign_file_handle(KEY, payload)
    token = security._b64encode(payload) + "." + security._b64encode(handle[-security.MAC_BYTES :])
    with pytest.raises(InvalidSignatureError):
        security.verify_access_token(KEY, token)


def test_file_handle() -> None:
    handle = security.sign_file_handle(KEY, b"contenido")
    assert security.verify_file_handle(KEY, handle) == b"contenido"
    with pytest.raises(InvalidSignatureError):
        security.verify_file_handle(KEY, b"x" + handle[1:])
    with pytest.raises(InvalidSignatureError):
        security.verify_file_handle(KEY, b"corto")


def test_block_token_checks() -> None:
    block_id = str(uuid.uuid4())
    read = common_pb2.BLOCK_OPERATION_READ
    token = security.create_block_token(KEY, block_id, read)
    assert security.check_block_token(KEY, token, block_id, read) is None
    assert security.check_block_token(OTHER_KEY, token, block_id, read) is not None
    assert security.check_block_token(KEY, token, str(uuid.uuid4()), read) is not None
    assert security.check_block_token(KEY, token, block_id, common_pb2.BLOCK_OPERATION_WRITE) is not None
    old = security.create_block_token(KEY, block_id, read, now=time.time() - security.BLOCK_TOKEN_TTL_S - 31)
    problem = security.check_block_token(KEY, old, block_id, read)
    assert problem is not None and problem.message == "caducado"
    tampered = common_pb2.BlockToken()
    tampered.CopyFrom(token)
    tampered.operation = common_pb2.BLOCK_OPERATION_WRITE
    assert security.check_block_token(KEY, tampered, block_id, common_pb2.BLOCK_OPERATION_WRITE) is not None


def test_password_hashing() -> None:
    salt, hashed = security.hash_password("contraseña correcta")
    assert security.verify_password("contraseña correcta", salt, hashed)
    assert not security.verify_password("otra", salt, hashed)
    other_salt, other_hash = security.hash_password("contraseña correcta")
    assert other_salt != salt and other_hash != hashed  # sal por usuario


def test_envelope_encryption() -> None:
    wrapping_key, data_key = security.generate_key(), security.generate_key()
    wrapped = security.wrap_data_key(wrapping_key, data_key, "file-1")
    assert security.unwrap_data_key(wrapping_key, wrapped, "file-1") == data_key
    with pytest.raises(InvalidSignatureError):
        security.unwrap_data_key(wrapping_key, wrapped, "file-2")  # ligada a su archivo
    block_id = str(uuid.uuid4())
    stored = security.encrypt_block(data_key, block_id, b"texto en claro" * 10)
    assert len(stored) == len(b"texto en claro" * 10) + security.ENCRYPTION_OVERHEAD_BYTES
    assert b"texto en claro" not in stored
    assert security.decrypt_block(data_key, block_id, stored) == b"texto en claro" * 10
    with pytest.raises(InvalidSignatureError):
        security.decrypt_block(data_key, str(uuid.uuid4()), stored)  # otro block_id: no se pueden intercambiar
    flipped = bytearray(stored)
    flipped[20] ^= 1
    with pytest.raises(InvalidSignatureError):
        security.decrypt_block(data_key, block_id, bytes(flipped))  # un solo bit cambiado
    assert security.encrypt_block(data_key, block_id, b"x") != security.encrypt_block(data_key, block_id, b"x")
