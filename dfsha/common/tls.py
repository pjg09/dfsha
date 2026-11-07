"""TLS de las conexiones gRPC: credenciales y rol del otro extremo (fase I §10.4, ADR 0023).

- TLS mutuo en todas las conexiones (ADR 0043): cada extremo presenta un certificado de la CA interna,
  también el cliente, que además autentica a su usuario con el token de acceso. gRPC para Python no
  permite pedir un certificado de cliente sin exigirlo, así que no hay término medio en un mismo puerto.
- El rol del otro extremo sale del SAN ``<rol>-<n>`` de su certificado.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import grpc

DEFAULT_SECRETS_DIRECTORY = "/run/secrets/dfsha"
_ROLE_NAME = re.compile(r"^(metadata|datanode|client)-[1-9][0-9]*$")
_MESSAGE_OPTIONS = [("grpc.max_receive_message_length", 4 * 1024 * 1024), ("grpc.max_send_message_length", 4 * 1024 * 1024)]


@dataclass(frozen=True)
class TlsIdentity:
    ca_cert: bytes
    cert: bytes | None = None
    key: bytes | None = None


def load_identity(directory: Path) -> TlsIdentity:
    """Lee ``ca.pem`` y, si existen, ``cert.pem`` y ``key.pem`` del directorio de secretos del host."""
    cert_path, key_path = directory / "cert.pem", directory / "key.pem"
    has_certificate = cert_path.exists() and key_path.exists()
    return TlsIdentity(
        ca_cert=(directory / "ca.pem").read_bytes(),
        cert=cert_path.read_bytes() if has_certificate else None,
        key=key_path.read_bytes() if has_certificate else None,
    )


def read_secret(directory: Path, name: str) -> bytes:
    return (directory / name).read_bytes()


def get_server_credentials(identity: TlsIdentity) -> grpc.ServerCredentials:
    if identity.cert is None or identity.key is None:
        raise ValueError("Un servidor necesita su certificado y su clave")
    return grpc.ssl_server_credentials(
        [(identity.key, identity.cert)], root_certificates=identity.ca_cert, require_client_auth=True
    )


def get_channel_credentials(identity: TlsIdentity) -> grpc.ChannelCredentials:
    """TLS mutuo hacia un servidor de la CA interna, con el certificado propio del host."""
    return grpc.ssl_channel_credentials(
        root_certificates=identity.ca_cert, private_key=identity.key, certificate_chain=identity.cert
    )


def make_channel_factory(identity: TlsIdentity) -> Callable[[str], grpc.Channel]:
    credentials = get_channel_credentials(identity)

    def create_channel(addr: str) -> grpc.Channel:
        return grpc.secure_channel(addr, credentials, options=_MESSAGE_OPTIONS)

    return create_channel


def get_peer_name(context: grpc.ServicerContext) -> str | None:
    """Nombre ``<rol>-<n>`` del certificado que presentó el otro extremo, o None."""
    for raw in context.auth_context().get("x509_subject_alternative_name", []):
        name = raw.decode() if isinstance(raw, bytes) else str(raw)
        if _ROLE_NAME.match(name):
            return name
    return None


def get_peer_role(context: grpc.ServicerContext) -> str | None:
    """Rol del certificado que presentó el otro extremo (``metadata``, ``datanode`` o ``client``), o None."""
    name = get_peer_name(context)
    return name.rpartition("-")[0] if name is not None else None
