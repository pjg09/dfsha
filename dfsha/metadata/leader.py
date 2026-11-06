"""Elección del líder de los servidores de metadatos sobre etcd (ADR 0039 y 0041).

- El líder tiene la clave ``leader`` ligada a un arrendamiento de etcd y la renueva periódicamente.
- **Época del líder:** la revisión en la que se creó esa clave. Crece en cada elección y sirve de
  ficha de cercado: cada transacción del líder la compara, y viaja en las órdenes a los nodos de datos.
- **Renuncia anticipada:** si no ha renovado el arrendamiento en ``step_down_after_s``, el líder deja de
  actuar como tal aunque etcd todavía no haya borrado la clave.
"""

import logging
import threading
import time
from collections.abc import Callable

from dfsha.etcd.rpc_pb2 import Compare
from dfsha.metadata.etcd_client import EtcdClient, EtcdError, compare_absent, compare_create_revision, op_get, op_put

logger = logging.getLogger(__name__)


class LeaderElection:
    def __init__(
        self,
        etcd: EtcdClient,
        key: bytes,
        self_addr: str,
        ttl_s: int = 5,
        refresh_interval_s: float = 1.0,
        step_down_after_s: float = 3.5,
        on_elected: Callable[[int], None] | None = None,
    ) -> None:
        if step_down_after_s >= ttl_s:
            raise ValueError("El líder tiene que renunciar antes de que caduque su arrendamiento")
        self._etcd = etcd
        self._key = key
        self._self_addr = self_addr
        self._ttl_s = ttl_s
        self._refresh_interval_s = refresh_interval_s
        self._step_down_after_s = step_down_after_s
        self._on_elected = on_elected
        self._lock = threading.Lock()
        self._stopped = threading.Event()
        self._thread: threading.Thread | None = None
        self._lease_id = 0
        self._epoch = 0
        self._last_refresh = 0.0  # reloj monótono: cuándo se pidió la última renovación que funcionó
        self._known_leader_addr = ""

    # ----- Estado ------------------------------------------------------------------------------

    @property
    def is_leader(self) -> bool:
        with self._lock:
            return self._epoch > 0 and time.monotonic() - self._last_refresh < self._step_down_after_s

    @property
    def epoch(self) -> int:
        """Época del líder; 0 si este servidor no es el líder."""
        with self._lock:
            return self._epoch if self.is_leader_unlocked() else 0

    def is_leader_unlocked(self) -> bool:
        return self._epoch > 0 and time.monotonic() - self._last_refresh < self._step_down_after_s

    def fencing_compare(self) -> Compare:
        """Comparación que toda transacción del líder incluye: la clave del líder sigue siendo suya."""
        epoch = self.epoch
        if epoch == 0:
            raise NotLeaderError(self.get_leader_addr())
        return compare_create_revision(self._key, epoch)

    def get_leader_addr(self) -> str:
        """Dirección del líder actual según etcd, o la última conocida si etcd no responde."""
        if self.is_leader:
            return self._self_addr
        try:
            kv, _ = self._etcd.get(self._key)
        except EtcdError:
            return self._known_leader_addr
        self._known_leader_addr = kv.value.decode() if kv is not None else ""
        return self._known_leader_addr

    def lose_leadership(self, reason: str) -> None:
        """Deja de ser líder ya; por ejemplo, si una transacción falló por la comparación de cercado."""
        with self._lock:
            if self._epoch == 0:
                return
            logger.warning("Deja de ser líder (época %d): %s", self._epoch, reason)
            self._epoch = 0

    # ----- Ciclo de vida -----------------------------------------------------------------------

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="leader-election", daemon=True)
        self._thread.start()

    def stop(self, resign: bool = True) -> None:
        """Para la elección. Con ``resign``, libera la clave para que otro sea líder sin esperar al TTL."""
        self._stopped.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        if resign and self._lease_id:
            try:
                self._etcd.revoke_lease(self._lease_id)
            except EtcdError:
                pass
        with self._lock:
            self._epoch = 0
            self._lease_id = 0

    def _run(self) -> None:
        while not self._stopped.is_set():
            try:
                if self._epoch and self._lease_id:
                    self._refresh()
                else:
                    self._campaign()
            except EtcdError as error:
                logger.warning("etcd no responde durante la elección: %s", error)
            self._stopped.wait(self._refresh_interval_s)

    def _campaign(self) -> None:
        lease_id = self._etcd.grant_lease(self._ttl_s)
        requested_at = time.monotonic()
        response = self._etcd.txn(
            [compare_absent(self._key)],
            [op_put(self._key, self._self_addr.encode(), lease_id)],
            [op_get(self._key)],
        )
        if not response.succeeded:
            self._etcd.revoke_lease(lease_id)
            kvs = response.responses[0].response_range.kvs
            self._known_leader_addr = kvs[0].value.decode() if kvs else ""
            return
        with self._lock:
            self._lease_id = lease_id
            self._epoch = response.header.revision  # revisión de creación de la clave
            self._last_refresh = requested_at
            epoch = self._epoch
        logger.info("Elegido líder con época %d", epoch)
        if self._on_elected is not None:
            self._on_elected(epoch)

    def _refresh(self) -> None:
        requested_at = time.monotonic()
        remaining_ttl_s = self._etcd.refresh_lease(self._lease_id)
        if remaining_ttl_s <= 0:
            self.lose_leadership("el arrendamiento de etcd caducó")
            self._lease_id = 0
            return
        with self._lock:
            if self._epoch:
                self._last_refresh = requested_at


class NotLeaderError(Exception):
    """Este servidor de metadatos no es el líder; ``leader_addr`` es el que se conoce."""

    def __init__(self, leader_addr: str) -> None:
        super().__init__(f"No es el líder; el líder es {leader_addr or 'desconocido'}")
        self.leader_addr = leader_addr
