"""Utilidades comunes de las pruebas."""

import socket
import time
from collections.abc import Callable
from typing import TypeVar

import grpc
import pytest

from dfsha.common.errors import DfshaError

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
