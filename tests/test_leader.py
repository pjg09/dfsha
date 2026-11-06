"""Elección del líder sobre un etcd real: un solo líder, relevo, renuncia anticipada y cercado (ADR 0039)."""

import time
from collections.abc import Callable, Iterator

import pytest

from dfsha.metadata.etcd_client import EtcdClient, op_put
from dfsha.metadata.leader import LeaderElection, NotLeaderError

# Tiempos cortos para que las pruebas no esperen los 5 s de producción
TTL_S = 2
STEP_DOWN_AFTER_S = 1.4
REFRESH_INTERVAL_S = 0.2


def _wait_until(condition: Callable[[], bool], timeout_s: float = 6) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def elections(etcd: EtcdClient, etcd_prefix: bytes) -> Iterator[list[LeaderElection]]:
    started = [
        LeaderElection(etcd, etcd_prefix + b"leader", f"metadata-{n}:50051", TTL_S, REFRESH_INTERVAL_S, STEP_DOWN_AFTER_S)
        for n in (1, 2, 3)
    ]
    for election in started:
        election.start()
    yield started
    for election in started:
        election.stop()


def _leaders(elections: list[LeaderElection]) -> list[LeaderElection]:
    return [election for election in elections if election.is_leader]


def test_exactly_one_leader(elections: list[LeaderElection]) -> None:
    assert _wait_until(lambda: len(_leaders(elections)) == 1)
    time.sleep(1)
    leaders = _leaders(elections)
    assert len(leaders) == 1
    leader_addr = leaders[0].get_leader_addr()
    assert all(election.get_leader_addr() == leader_addr for election in elections)


def test_new_leader_with_higher_epoch_after_resignation(elections: list[LeaderElection]) -> None:
    assert _wait_until(lambda: len(_leaders(elections)) == 1)
    old = _leaders(elections)[0]
    old_epoch = old.epoch
    old.stop(resign=True)
    others = [election for election in elections if election is not old]
    assert _wait_until(lambda: len(_leaders(others)) == 1)
    assert _leaders(others)[0].epoch > old_epoch


def test_crashed_leader_is_replaced_after_ttl(elections: list[LeaderElection]) -> None:
    # Sin revocar el arrendamiento, como si el proceso muriera: el relevo llega cuando caduca
    assert _wait_until(lambda: len(_leaders(elections)) == 1)
    old = _leaders(elections)[0]
    old.stop(resign=False)
    others = [election for election in elections if election is not old]
    started = time.monotonic()
    assert _wait_until(lambda: len(_leaders(others)) == 1, timeout_s=TTL_S + 4)
    assert time.monotonic() - started >= STEP_DOWN_AFTER_S - 0.5


def test_paused_leader_steps_down_before_its_ttl(etcd: EtcdClient, etcd_prefix: bytes) -> None:
    election = LeaderElection(etcd, etcd_prefix + b"leader", "metadata-1:50051", TTL_S, REFRESH_INTERVAL_S, STEP_DOWN_AFTER_S)
    election.start()
    try:
        assert _wait_until(lambda: election.is_leader)
        election._stopped.set()  # simula un proceso en pausa: deja de renovar sin enterarse
        time.sleep(STEP_DOWN_AFTER_S + 0.2)
        assert not election.is_leader
        with pytest.raises(NotLeaderError):
            election.fencing_compare()
    finally:
        election.stop()


def test_fencing_rejects_writes_of_a_deposed_leader(elections: list[LeaderElection], etcd: EtcdClient, etcd_prefix: bytes) -> None:
    assert _wait_until(lambda: len(_leaders(elections)) == 1)
    old = _leaders(elections)[0]
    fencing = old.fencing_compare()  # comparación tomada mientras era líder
    old.stop(resign=True)
    others = [election for election in elections if election is not old]
    assert _wait_until(lambda: len(_leaders(others)) == 1)
    late_write = etcd.txn([fencing], [op_put(etcd_prefix + b"dato", "del líder depuesto".encode())])
    assert not late_write.succeeded
    assert etcd.get(etcd_prefix + b"dato")[0] is None
    new_write = etcd.txn([_leaders(others)[0].fencing_compare()], [op_put(etcd_prefix + b"dato", "del líder nuevo".encode())])
    assert new_write.succeeded
