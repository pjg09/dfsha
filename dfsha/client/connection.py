"""Conexión del cliente con el líder de metadatos y con los nodos de datos (§3.5, ADR 0020 y 0021).

El cliente solo conoce las direcciones de los servidores de metadatos. Si le responde un seguidor, repite
en el líder que indica NODE_NOT_LEADER. Los fallos transitorios (UNAVAILABLE, DEADLINE_EXCEEDED) se
reintentan con espera exponencial y la misma petición, es decir, con el mismo ``request_id``: el servidor
devuelve la respuesta guardada si ya la aplicó (§8.6).
"""

import logging
import random
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar

import grpc

from dfsha.common.errors import DfshaError, Reason
from dfsha.v1 import datanode_pb2_grpc, metadata_pb2_grpc

logger = logging.getLogger(__name__)

T = TypeVar("T")

_RETRYABLE_CODES = (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED)
_MESSAGE_OPTIONS = [("grpc.max_receive_message_length", 4 * 1024 * 1024), ("grpc.max_send_message_length", 4 * 1024 * 1024)]


@dataclass(frozen=True)
class RetryPolicy:
    """Reintentos con espera exponencial y fluctuación aleatoria.

    El tope total queda muy por debajo de los 10 min que el servidor recuerda un ``request_id``: un
    duplicado que llegara después no se detectaría (§8.6).
    """

    max_attempts: int = 8
    initial_backoff_s: float = 0.2
    max_backoff_s: float = 5.0
    max_total_s: float = 120.0

    def get_backoff_s(self, attempt: int) -> float:
        backoff = min(self.max_backoff_s, self.initial_backoff_s * 2**attempt)
        return backoff * random.uniform(0.5, 1.0)


class ChannelPool:
    """Un canal gRPC por dirección, reutilizado entre llamadas."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._channels: dict[str, grpc.Channel] = {}

    def get(self, addr: str) -> grpc.Channel:
        with self._lock:
            channel = self._channels.get(addr)
            if channel is None:
                channel = self._channels[addr] = grpc.insecure_channel(addr, options=_MESSAGE_OPTIONS)  # TLS: etapa 6
            return channel

    def close(self) -> None:
        with self._lock:
            for channel in self._channels.values():
                channel.close()
            self._channels.clear()


class MetadataConnection:
    def __init__(self, metadata_addrs: Sequence[str], channels: ChannelPool, timeout_s: float, retry: RetryPolicy) -> None:
        if not metadata_addrs:
            raise ValueError("Hace falta al menos una dirección de servidor de metadatos (DFSHA_METADATA_ADDRS)")
        self._addrs = list(metadata_addrs)
        self._channels = channels
        self._timeout_s = timeout_s
        self._retry = retry
        self._leader_addr = self._addrs[0]
        self._lock = threading.Lock()

    def call(self, operation: Callable[[metadata_pb2_grpc.MetadataServiceStub, float], T]) -> T:
        """Ejecuta una llamada en el líder, con redirecciones y reintentos.

        ``operation`` recibe el stub y el plazo, y tiene que construir siempre la misma petición: así un
        reintento lleva el mismo ``request_id``.
        """
        started = time.monotonic()
        attempt = 0
        redirects = 0
        while True:
            with self._lock:
                addr = self._leader_addr
            try:
                return operation(metadata_pb2_grpc.MetadataServiceStub(self._channels.get(addr)), self._timeout_s)
            except grpc.RpcError as rpc_error:
                error = DfshaError.from_rpc_error(rpc_error)
                leader_addr = error.metadata.get("leader_addr", "")
                if error.reason is Reason.NODE_NOT_LEADER and leader_addr and leader_addr != addr and redirects < len(self._addrs):
                    redirects += 1
                    self._set_leader(leader_addr)
                    continue  # redirección inmediata, sin esperar
                if error.code not in _RETRYABLE_CODES:
                    raise error from rpc_error
                attempt += 1
                if attempt >= self._retry.max_attempts or time.monotonic() - started > self._retry.max_total_s:
                    raise error from rpc_error
                if error.reason is not Reason.NODE_NOT_LEADER and error.reason is not Reason.QUORUM_NOT_REACHED:
                    self._switch_server(addr)  # el servidor no responde: prueba otro
                redirects = 0
                backoff_s = self._retry.get_backoff_s(attempt)
                logger.info("Reintento %d en %.1f s: %s", attempt, backoff_s, error.message)
                time.sleep(backoff_s)

    def _set_leader(self, addr: str) -> None:
        with self._lock:
            self._leader_addr = addr

    def _switch_server(self, failed_addr: str) -> None:
        with self._lock:
            if self._leader_addr != failed_addr:
                return
            others = [addr for addr in self._addrs if addr != failed_addr] or self._addrs
            self._leader_addr = random.choice(others)


def get_datanode_stub(channels: ChannelPool, addr: str) -> datanode_pb2_grpc.DataNodeServiceStub:
    return datanode_pb2_grpc.DataNodeServiceStub(channels.get(addr))
