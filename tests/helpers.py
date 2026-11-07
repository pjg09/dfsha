"""Utilidades comunes de las pruebas."""

import collections
import socket
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import grpc
import pytest

from dfsha.common import tls
from dfsha.common.errors import DfshaError
from dfsha.common.security import AUTHORIZATION_HEADER
from dfsha.v1 import metadata_pb2, metadata_pb2_grpc

T = TypeVar("T")


def get_free_addr() -> str:
    """Dirección localhost:<puerto> libre en este momento."""
    with socket.socket() as probe:
        probe.bind(("localhost", 0))
        return f"localhost:{probe.getsockname()[1]}"


def start_on_free_addr(start: Callable[[str], T], attempts: int = 5) -> T:
    """Arranca un servidor en una dirección libre; si otro proceso tomó el puerto entre medias, prueba otra."""
    for attempt in range(attempts):
        try:
            return start(get_free_addr())
        except RuntimeError as error:  # grpc: «Failed to bind to address»
            if "bind" not in str(error).lower() or attempt == attempts - 1:
                raise
    raise AssertionError("inalcanzable")


def wait_until(condition: Callable[[], bool], timeout_s: float = 6) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return False


def expect_error(call: Callable[[], object]) -> DfshaError:
    """Ejecuta una llamada gRPC que tiene que fallar y devuelve el error con su motivo."""
    with pytest.raises(grpc.RpcError) as raised:
        call()
    return DfshaError.from_rpc_error(raised.value)


def secure_channel(secrets: Path, host: str, addr: str) -> grpc.Channel:
    """Canal con TLS mutuo, presentando el certificado de ``host`` (ADR 0043)."""
    return tls.make_channel_factory(tls.load_identity(secrets / host))(addr)


class _CallDetails(
    collections.namedtuple("_CallDetails", ("method", "timeout", "metadata", "credentials", "wait_for_ready", "compression")),
    grpc.ClientCallDetails,
):
    pass


class _TokenInterceptor(grpc.UnaryUnaryClientInterceptor):
    """Añade el token de acceso a cada llamada, como hace el cliente de verdad."""

    def __init__(self, token: str) -> None:
        self.token = token

    def intercept_unary_unary(self, continuation, client_call_details, request):  # type: ignore[no-untyped-def]  # noqa: ANN001, ANN201
        metadata = [*(client_call_details.metadata or []), (AUTHORIZATION_HEADER, f"Bearer {self.token}")]
        details = _CallDetails(
            client_call_details.method, client_call_details.timeout, metadata,
            client_call_details.credentials, client_call_details.wait_for_ready, client_call_details.compression,
        )  # fmt: skip
        return continuation(details, request)


def with_token(channel: grpc.Channel, token: str) -> grpc.Channel:
    return grpc.intercept_channel(channel, _TokenInterceptor(token))


def authenticate(channel: grpc.Channel, username: str, password: str, timeout_s: float = 10) -> str:
    """Token de acceso; espera a que haya líder y a que exista el usuario (el admin se crea al elegir líder)."""
    stub = metadata_pb2_grpc.MetadataServiceStub(channel)
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            request = metadata_pb2.AuthenticateRequest(username=username, password=password)
            return stub.Authenticate(request, timeout=5).access_token
        except grpc.RpcError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.1)


def admin_password(secrets: Path) -> str:
    return (secrets / "admin-password").read_text().strip()

