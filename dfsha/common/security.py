"""Primitivas de seguridad comunes (fase I §10; ADR 0022, 0024 y 0043).

- Firmas HMAC-SHA256 con separación de dominios: cada tipo de dato firmado lleva su propio prefijo, para que
  una firma válida de un tipo no sirva para otro aunque se use la misma clave.
- Contraseñas con scrypt y una sal por usuario.
- Cifrado de sobre: la clave de datos de cada archivo se envuelve con AES-256-GCM y la clave de envoltura;
  cada bloque se cifra con AES-256-GCM, un nonce aleatorio y el ``block_id`` como dato asociado.
"""

import base64
import hashlib
import hmac
import os
import time
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from google.protobuf.timestamp_pb2 import Timestamp

from dfsha.v1 import common_pb2
from dfsha.v1.records_pb2 import AccessTokenClaims

ACCESS_TOKEN_TTL_S = 3600  # 1 h (§10.2)
BLOCK_TOKEN_TTL_S = 600  # 10 min (§10.3)
CLOCK_SKEW_TOLERANCE_S = 30  # margen de reloj (§10.6, ADR 0033)
KEY_BYTES = 32  # claves de 256 bits
NONCE_BYTES = 12  # nonce de 96 bits (§10.5)
TAG_BYTES = 16
ENCRYPTION_OVERHEAD_BYTES = NONCE_BYTES + TAG_BYTES  # 28 bytes por bloque
MAC_BYTES = 32
AUTHORIZATION_HEADER = "authorization"

_ACCESS_TOKEN_DOMAIN = b"dfsha/v1/access-token"
_FILE_HANDLE_DOMAIN = b"dfsha/v1/file-handle"
_BLOCK_TOKEN_DOMAIN = b"dfsha/v1/block-token"

# scrypt: 2^15 iteraciones, 32 MiB de memoria por cálculo (§10.2)
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**15, 8, 1


class InvalidSignatureError(ValueError):
    """La firma no corresponde al contenido: dato alterado o fabricado."""


def _mac(key: bytes, domain: bytes, payload: bytes) -> bytes:
    return hmac.new(key, domain + b"\0" + payload, hashlib.sha256).digest()


def _timestamp(seconds: float) -> Timestamp:
    timestamp = Timestamp()
    timestamp.FromNanoseconds(int(seconds * 1e9))
    return timestamp


def _seconds(timestamp: Timestamp) -> float:
    return timestamp.ToNanoseconds() / 1e9


def is_expired(expires_at: Timestamp, now: float | None = None) -> bool:
    """Caducado, con el margen de reloj de la §10.6: un token se acepta hasta 30 s después."""
    current = time.time() if now is None else now
    return current > _seconds(expires_at) + CLOCK_SKEW_TOLERANCE_S


def generate_key() -> bytes:
    return os.urandom(KEY_BYTES)


# ----- Token de acceso ---------------------------------------------------------------------------


def create_access_token(key: bytes, user_id: str, is_admin: bool, now: float | None = None) -> tuple[str, Timestamp]:
    expires_at = _timestamp((time.time() if now is None else now) + ACCESS_TOKEN_TTL_S)
    payload = AccessTokenClaims(user_id=user_id, is_admin=is_admin, expires_at=expires_at).SerializeToString(deterministic=True)
    token = _b64encode(payload) + "." + _b64encode(_mac(key, _ACCESS_TOKEN_DOMAIN, payload))
    return token, expires_at


def verify_access_token(key: bytes, token: str) -> AccessTokenClaims:
    """Devuelve las afirmaciones del token. Lanza InvalidSignatureError si no es válido; no mira la caducidad."""
    try:
        encoded_payload, encoded_mac = token.split(".")
        payload, mac = _b64decode(encoded_payload), _b64decode(encoded_mac)
    except ValueError:
        raise InvalidSignatureError("Token de acceso mal formado") from None
    if not hmac.compare_digest(mac, _mac(key, _ACCESS_TOKEN_DOMAIN, payload)):
        raise InvalidSignatureError("Firma del token de acceso no válida")
    return AccessTokenClaims.FromString(payload)


# ----- Descriptor de archivo ---------------------------------------------------------------------


def sign_file_handle(key: bytes, payload: bytes) -> bytes:
    """El descriptor que recibe el cliente: contenido seguido de su firma (§10.3)."""
    return payload + _mac(key, _FILE_HANDLE_DOMAIN, payload)


def verify_file_handle(key: bytes, file_handle: bytes) -> bytes:
    payload, mac = file_handle[:-MAC_BYTES], file_handle[-MAC_BYTES:]
    if len(file_handle) <= MAC_BYTES or not hmac.compare_digest(mac, _mac(key, _FILE_HANDLE_DOMAIN, payload)):
        raise InvalidSignatureError("Descriptor de archivo no válido")
    return payload


# ----- Token de bloque ---------------------------------------------------------------------------


def _block_token_payload(token: common_pb2.BlockToken) -> bytes:
    unsigned = common_pb2.BlockToken()
    unsigned.CopyFrom(token)
    unsigned.ClearField("signature")
    return unsigned.SerializeToString(deterministic=True)


def create_block_token(
    key: bytes, block_id: str, operation: common_pb2.BlockOperation, now: float | None = None
) -> common_pb2.BlockToken:
    token = common_pb2.BlockToken(
        block_id=block_id, operation=operation, expires_at=_timestamp((time.time() if now is None else now) + BLOCK_TOKEN_TTL_S)
    )
    token.signature = _mac(key, _BLOCK_TOKEN_DOMAIN, _block_token_payload(token))
    return token


@dataclass(frozen=True)
class BlockTokenProblem:
    message: str


def check_block_token(
    key: bytes, token: common_pb2.BlockToken, block_id: str, operation: common_pb2.BlockOperation, now: float | None = None
) -> BlockTokenProblem | None:
    """Comprueba firma, bloque, operación y caducidad sin consultar a nadie (§10.3). None si es válido."""
    if not token.signature or not hmac.compare_digest(token.signature, _mac(key, _BLOCK_TOKEN_DOMAIN, _block_token_payload(token))):
        return BlockTokenProblem("firma no válida")
    if token.block_id != block_id:
        return BlockTokenProblem("es de otro bloque")
    if token.operation != operation:
        return BlockTokenProblem("es de otra operación")
    if is_expired(token.expires_at, now):
        return BlockTokenProblem("caducado")
    return None


# ----- Contraseñas -------------------------------------------------------------------------------


def hash_password(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """Devuelve (sal, hash) con scrypt y una sal aleatoria de 16 bytes."""
    used_salt = salt if salt is not None else os.urandom(16)
    kdf = Scrypt(salt=used_salt, length=32, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return used_salt, kdf.derive(password.encode())


def verify_password(password: str, salt: bytes, expected_hash: bytes) -> bool:
    _, computed = hash_password(password, salt)
    return hmac.compare_digest(computed, expected_hash)


# ----- Cifrado de sobre --------------------------------------------------------------------------


def wrap_data_key(wrapping_key: bytes, data_key: bytes, file_id: str) -> bytes:
    """Envuelve la clave de datos de un archivo; el ``file_id`` la liga a ese archivo."""
    nonce = os.urandom(NONCE_BYTES)
    return nonce + AESGCM(wrapping_key).encrypt(nonce, data_key, file_id.encode())


def unwrap_data_key(wrapping_key: bytes, wrapped: bytes, file_id: str) -> bytes:
    try:
        return AESGCM(wrapping_key).decrypt(wrapped[:NONCE_BYTES], wrapped[NONCE_BYTES:], file_id.encode())
    except InvalidTag:
        raise InvalidSignatureError("La clave de datos envuelta no corresponde a este archivo") from None


def encrypt_block(data_key: bytes, block_id: str, plaintext: bytes) -> bytes:
    """Bloque guardado: nonce ‖ texto cifrado ‖ etiqueta, 28 bytes más que el bloque en claro (§10.5)."""
    nonce = os.urandom(NONCE_BYTES)
    return nonce + AESGCM(data_key).encrypt(nonce, plaintext, block_id.encode())


def decrypt_block(data_key: bytes, block_id: str, stored: bytes) -> bytes:
    """Descifra y verifica la etiqueta GCM: falla si ha cambiado un solo bit o si es de otro bloque."""
    try:
        return AESGCM(data_key).decrypt(stored[:NONCE_BYTES], stored[NONCE_BYTES:], block_id.encode())
    except InvalidTag:
        raise InvalidSignatureError(f"El bloque {block_id} no supera la verificación de AES-GCM") from None


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
