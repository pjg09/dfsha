"""Los errores viajan por gRPC con su código de estado y su código de motivo (fase I §5.4)."""

from collections.abc import Iterator
from concurrent import futures

import grpc
import pytest
from google.rpc import code_pb2

from dfsha.common.errors import DfshaError, Reason

_METHOD = "/dfsha.test.Errors/Fail"


class _FailingHandler(grpc.GenericRpcHandler):
    """Servicio de prueba que responde con el error que se le indique."""

    def __init__(self) -> None:
        self.error: DfshaError | None = None

    def service(self, handler_call_details: grpc.HandlerCallDetails) -> grpc.RpcMethodHandler | None:
        if getattr(handler_call_details, "method", None) != _METHOD:
            return None

        def fail(_request: bytes, context: grpc.ServicerContext) -> bytes:
            assert self.error is not None
            context.abort_with_status(self.error.to_status())

        return grpc.unary_unary_rpc_method_handler(fail)


@pytest.fixture
def server() -> Iterator[tuple[_FailingHandler, grpc.Channel]]:
    handler = _FailingHandler()
    grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    grpc_server.add_generic_rpc_handlers((handler,))
    port = grpc_server.add_insecure_port("localhost:0")
    grpc_server.start()
    channel = grpc.insecure_channel(f"localhost:{port}")
    try:
        yield handler, channel
    finally:
        channel.close()
        grpc_server.stop(grace=None)


def _call(channel: grpc.Channel) -> DfshaError:
    call = channel.unary_unary(_METHOD)
    with pytest.raises(grpc.RpcError) as raised:
        call(b"", timeout=5)
    return DfshaError.from_rpc_error(raised.value)


def test_reason_and_metadata_cross_the_wire(server: tuple[_FailingHandler, grpc.Channel]) -> None:
    handler, channel = server
    handler.error = DfshaError(
        grpc.StatusCode.UNAVAILABLE,
        "Este servidor de metadatos no es el líder",
        Reason.NODE_NOT_LEADER,
        {"leader_addr": "metadata-2:50051"},
    )
    received = _call(channel)
    assert received.code is grpc.StatusCode.UNAVAILABLE
    assert received.reason is Reason.NODE_NOT_LEADER
    assert received.metadata == {"leader_addr": "metadata-2:50051"}
    assert received.message == "Este servidor de metadatos no es el líder"


def test_same_reason_with_different_codes(server: tuple[_FailingHandler, grpc.Channel]) -> None:
    # BLOCK_CORRUPTED es ABORTED al escribir y DATA_LOSS al leer (Tabla 20)
    handler, channel = server
    for code in (grpc.StatusCode.ABORTED, grpc.StatusCode.DATA_LOSS):
        handler.error = DfshaError(code, "El hash del bloque no coincide", Reason.BLOCK_CORRUPTED)
        received = _call(channel)
        assert (received.code, received.reason) == (code, Reason.BLOCK_CORRUPTED)


def test_error_without_reason(server: tuple[_FailingHandler, grpc.Channel]) -> None:
    handler, channel = server
    handler.error = DfshaError(grpc.StatusCode.DEADLINE_EXCEEDED, "Plazo agotado")
    received = _call(channel)
    assert received.code is grpc.StatusCode.DEADLINE_EXCEEDED
    assert received.reason is None


def test_plain_grpc_error_has_no_reason(server: tuple[_FailingHandler, grpc.Channel]) -> None:
    _, channel = server
    call = channel.unary_unary("/dfsha.test.Errors/NoExiste")
    with pytest.raises(grpc.RpcError) as raised:
        call(b"", timeout=5)
    received = DfshaError.from_rpc_error(raised.value)
    assert received.code is grpc.StatusCode.UNIMPLEMENTED
    assert received.reason is None


def test_reasons_match_table_20() -> None:
    assert len(Reason) == 16
    assert all(reason.value == reason.name for reason in Reason)


def test_grpc_codes_match_google_rpc() -> None:
    assert grpc.StatusCode.ABORTED.value[0] == code_pb2.ABORTED
    assert grpc.StatusCode.DATA_LOSS.value[0] == code_pb2.DATA_LOSS
