"""TLS real en localhost: rol del certificado, TLS mutuo y rechazo de certificados ajenos."""

from concurrent import futures
from pathlib import Path

import grpc
import pytest
from helpers import start_on_free_addr

from dfsha.common import pki, tls

_METHOD = "/dfsha.test.Tls/WhoAmI"


class _WhoAmI(grpc.GenericRpcHandler):
    def service(self, handler_call_details: grpc.HandlerCallDetails) -> grpc.RpcMethodHandler | None:
        if getattr(handler_call_details, "method", None) != _METHOD:
            return None
        def who_am_i(_request: bytes, context: grpc.ServicerContext) -> bytes:
            values = context.auth_context().get("ssl_tls_version") or []
            version = values[0].decode() if isinstance(values, list) and values else "?"
            return f"{tls.get_peer_role(context) or '-'}|{version}".encode()

        return grpc.unary_unary_rpc_method_handler(who_am_i)


@pytest.fixture(scope="module")
def secrets_directory(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("secretos")
    pki.create_cluster_secrets(directory, ["metadata-1", "datanode-1", "client-1"], extra_names=["localhost"])
    return directory


def _serve(identity: tls.TlsIdentity) -> tuple[grpc.Server, str]:
    def start(addr: str) -> tuple[grpc.Server, str]:
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        server.add_generic_rpc_handlers((_WhoAmI(),))
        server.add_secure_port(addr, tls.get_server_credentials(identity))
        return server, addr

    server, addr = start_on_free_addr(start)
    server.start()
    return server, addr


def _ask(addr: str, identity: tls.TlsIdentity) -> str:
    with grpc.secure_channel(addr, tls.get_channel_credentials(identity)) as channel:
        return channel.unary_unary(_METHOD)(b"", timeout=5).decode()


def test_secrets_layout(secrets_directory: Path) -> None:
    assert (secrets_directory / "metadata-1" / "wrapping.key").stat().st_mode & 0o777 == 0o600
    assert (secrets_directory / "datanode-1" / "block-token.key").exists()
    assert not (secrets_directory / "datanode-1" / "wrapping.key").exists()  # la clave de envoltura solo en metadatos
    assert (secrets_directory / "client-1" / "key.pem").exists()  # TLS mutuo también para el cliente
    assert not (secrets_directory / "client-1" / "block-token.key").exists()
    assert (secrets_directory / "admin-password").read_bytes()
    with pytest.raises(ValueError):
        pki.get_role("servidor-raro")


def test_peer_role_comes_from_the_certificate(secrets_directory: Path) -> None:
    server, addr = _serve(tls.load_identity(secrets_directory / "metadata-1"))
    try:
        assert _ask(addr, tls.load_identity(secrets_directory / "datanode-1")) == "datanode|TLSv1.3"
        assert _ask(addr, tls.load_identity(secrets_directory / "client-1")) == "client|TLSv1.3"  # TLS 1.3 (§10.4)
        without_certificate = tls.TlsIdentity(ca_cert=(secrets_directory / "client-1" / "ca.pem").read_bytes())
        with pytest.raises(grpc.RpcError):
            _ask(addr, without_certificate)  # sin certificado de la CA no hay conexión
    finally:
        server.stop(grace=None)


def test_foreign_ca_is_rejected(secrets_directory: Path, tmp_path: Path) -> None:
    pki.create_cluster_secrets(tmp_path, ["datanode-9"], extra_names=["localhost"])
    server, addr = _serve(tls.load_identity(secrets_directory / "metadata-1"))
    try:
        with pytest.raises(grpc.RpcError) as raised:
            _ask(addr, tls.load_identity(tmp_path / "datanode-9"))  # otra CA: el servidor no es de confianza
        assert raised.value.code() is grpc.StatusCode.UNAVAILABLE  # type: ignore[attr-defined]
    finally:
        server.stop(grace=None)


def test_plaintext_client_cannot_talk_to_tls_server(secrets_directory: Path) -> None:
    server, addr = _serve(tls.load_identity(secrets_directory / "metadata-1"))
    try:
        with grpc.insecure_channel(addr) as channel, pytest.raises(grpc.RpcError):
            channel.unary_unary(_METHOD)(b"", timeout=3)
    finally:
        server.stop(grace=None)
