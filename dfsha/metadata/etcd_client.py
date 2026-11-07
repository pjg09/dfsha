"""Cliente mínimo de etcd sobre el subconjunto de su API v3 (ADR 0041).

Ofrece lo que usa el servidor de metadatos: lecturas en una revisión, transacciones con
comparaciones y arrendamientos de etcd. Si un miembro de etcd no responde, prueba con el siguiente.
"""

import logging
import threading
from collections.abc import Callable, Iterator, Sequence
from typing import TypeVar

import grpc

from dfsha.etcd import rpc_pb2, rpc_pb2_grpc
from dfsha.etcd.rpc_pb2 import Compare, KeyValue, RequestOp

logger = logging.getLogger(__name__)

T = TypeVar("T")

class EtcdError(RuntimeError):
    """etcd no respondió en ninguno de sus miembros."""


def get_prefix_end(prefix: bytes) -> bytes:
    """Primera clave que ya no empieza por ``prefix``: el ``range_end`` de un rango por prefijo."""
    end = bytearray(prefix)
    for index in reversed(range(len(end))):
        if end[index] < 0xFF:
            end[index] += 1
            return bytes(end[: index + 1])
    return b"\0"  # todo el espacio de claves


# ----- Comparaciones y operaciones de una transacción --------------------------------------------


def compare_create_revision(key: bytes, revision: int) -> Compare:
    """La clave se creó en ``revision``; con 0, la clave no existe."""
    return Compare(key=key, target=Compare.CREATE, result=Compare.EQUAL, create_revision=revision)


def compare_mod_revision(key: bytes, revision: int) -> Compare:
    """La clave no ha cambiado desde ``revision``; con 0, la clave no existe."""
    return Compare(key=key, target=Compare.MOD, result=Compare.EQUAL, mod_revision=revision)


def compare_absent(key: bytes) -> Compare:
    return compare_create_revision(key, 0)


def compare_prefix_empty(prefix: bytes) -> Compare:
    """Ninguna clave empieza por ``prefix``: todas las del rango tendrían versión 0."""
    return Compare(
        key=prefix, range_end=get_prefix_end(prefix), target=Compare.VERSION, result=Compare.EQUAL, version=0
    )


def op_put(key: bytes, value: bytes, lease_id: int = 0) -> RequestOp:
    return RequestOp(request_put=rpc_pb2.PutRequest(key=key, value=value, lease=lease_id))


def op_delete(key: bytes) -> RequestOp:
    return RequestOp(request_delete_range=rpc_pb2.DeleteRangeRequest(key=key))


def op_delete_prefix(prefix: bytes) -> RequestOp:
    return RequestOp(request_delete_range=rpc_pb2.DeleteRangeRequest(key=prefix, range_end=get_prefix_end(prefix)))


def op_get(key: bytes) -> RequestOp:
    return RequestOp(request_range=rpc_pb2.RangeRequest(key=key))


class EtcdClient:
    def __init__(
        self,
        addrs: Sequence[str],
        timeout_s: float = 2.0,
        create_channel: Callable[[str], grpc.Channel] = grpc.insecure_channel,
    ) -> None:
        """``create_channel`` crea el canal hacia un miembro; en producción, con TLS mutuo (ADR 0039)."""
        if not addrs:
            raise ValueError("Hace falta al menos una dirección de etcd")
        self._addrs = list(addrs)
        self._timeout_s = timeout_s
        self._create_channel = create_channel
        self._lock = threading.Lock()
        self._current = 0
        self._channel = create_channel(self._addrs[0])

    def close(self) -> None:
        with self._lock:
            self._channel.close()

    # ----- Claves --------------------------------------------------------------------------------

    def get(self, key: bytes, revision: int = 0) -> tuple[KeyValue | None, int]:
        """Devuelve la clave (o None) y la revisión de etcd en la que se leyó. Lectura linealizable."""
        response = self._call(lambda kv, _: kv.Range(rpc_pb2.RangeRequest(key=key, revision=revision), timeout=self._timeout_s))
        return (response.kvs[0] if response.kvs else None), response.header.revision

    def get_prefix(self, prefix: bytes, revision: int = 0, limit: int = 0) -> tuple[list[KeyValue], int]:
        """Claves que empiezan por ``prefix``, en orden, y la revisión en la que se leyeron."""
        request = rpc_pb2.RangeRequest(key=prefix, range_end=get_prefix_end(prefix), revision=revision, limit=limit)
        response = self._call(lambda kv, _: kv.Range(request, timeout=self._timeout_s))
        return list(response.kvs), response.header.revision

    def count_prefix(self, prefix: bytes, revision: int = 0) -> int:
        request = rpc_pb2.RangeRequest(key=prefix, range_end=get_prefix_end(prefix), revision=revision, count_only=True)
        return self._call(lambda kv, _: kv.Range(request, timeout=self._timeout_s)).count

    def put(self, key: bytes, value: bytes, lease_id: int = 0) -> int:
        request = rpc_pb2.PutRequest(key=key, value=value, lease=lease_id)
        return self._call(lambda kv, _: kv.Put(request, timeout=self._timeout_s)).header.revision

    def txn(
        self, compare: Sequence[Compare], success: Sequence[RequestOp], failure: Sequence[RequestOp] = ()
    ) -> rpc_pb2.TxnResponse:
        """Transacción atómica: si todas las comparaciones se cumplen aplica ``success``; si no, ``failure``.

        Una transacción es una sola entrada del log replicado de etcd (fase I §4.2).
        """
        request = rpc_pb2.TxnRequest(compare=compare, success=success, failure=failure)
        return self._call(lambda kv, _: kv.Txn(request, timeout=self._timeout_s))

    # ----- Arrendamientos de etcd ----------------------------------------------------------------

    def grant_lease(self, ttl_s: int) -> int:
        response = self._call(lambda _, lease: lease.LeaseGrant(rpc_pb2.LeaseGrantRequest(TTL=ttl_s), timeout=self._timeout_s))
        if response.error:
            raise EtcdError(f"etcd no concedió el arrendamiento: {response.error}")
        return response.ID

    def revoke_lease(self, lease_id: int) -> None:
        """Revoca un arrendamiento de etcd y borra sus claves. Si ya no existe, no hace nada."""
        try:
            self._call(lambda _, lease: lease.LeaseRevoke(rpc_pb2.LeaseRevokeRequest(ID=lease_id), timeout=self._timeout_s))
        except grpc.RpcError as error:
            if not (isinstance(error, grpc.Call) and error.code() is grpc.StatusCode.NOT_FOUND):
                raise

    def refresh_lease(self, lease_id: int) -> int:
        """Renueva un arrendamiento de etcd. Devuelve su TTL restante; 0 si ya caducó."""

        def keep_alive(_: rpc_pb2_grpc.KVStub, lease: rpc_pb2_grpc.LeaseStub) -> int:
            requests: Iterator[rpc_pb2.LeaseKeepAliveRequest] = iter([rpc_pb2.LeaseKeepAliveRequest(ID=lease_id)])
            for response in lease.LeaseKeepAlive(requests, timeout=self._timeout_s):
                return response.TTL
            return 0

        return self._call(keep_alive)

    # ----- Conexión ------------------------------------------------------------------------------

    def _call(self, operation: Callable[[rpc_pb2_grpc.KVStub, rpc_pb2_grpc.LeaseStub], T]) -> T:
        """Ejecuta la operación y, si el miembro no está disponible, la repite en los demás."""
        last_error: grpc.RpcError | None = None
        for _ in range(len(self._addrs)):
            with self._lock:
                channel = self._channel
            try:
                return operation(rpc_pb2_grpc.KVStub(channel), rpc_pb2_grpc.LeaseStub(channel))
            except grpc.RpcError as error:
                code = error.code() if isinstance(error, grpc.Call) else None
                if code not in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
                    raise
                last_error = error
                self._switch_member(channel)
        raise EtcdError(f"Ningún miembro de etcd responde ({', '.join(self._addrs)})") from last_error

    def _switch_member(self, failed_channel: grpc.Channel) -> None:
        with self._lock:
            if self._channel is not failed_channel:
                return  # otro hilo ya cambió de miembro
            self._current = (self._current + 1) % len(self._addrs)
            failed_channel.close()
            self._channel = self._create_channel(self._addrs[self._current])
            logger.warning("Cambio al miembro de etcd %s", self._addrs[self._current])
