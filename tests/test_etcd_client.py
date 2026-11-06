"""Cliente de etcd contra un etcd v3.7.3 real: lecturas, transacciones y arrendamientos (ADR 0041)."""

import socket

from dfsha.metadata.etcd_client import (
    EtcdClient,
    compare_absent,
    compare_mod_revision,
    get_prefix_end,
    op_delete_prefix,
    op_get,
    op_put,
)


def test_prefix_end() -> None:
    assert get_prefix_end(b"/a/") == b"/a0"
    assert get_prefix_end(b"a\xff") == b"b"
    assert get_prefix_end(b"\xff\xff") == b"\0"


def test_put_and_get(etcd: EtcdClient, etcd_prefix: bytes) -> None:
    key = etcd_prefix + b"clave"
    assert etcd.get(key)[0] is None
    revision = etcd.put(key, b"valor")
    kv, read_revision = etcd.get(key)
    assert kv is not None and kv.value == b"valor"
    assert kv.create_revision == kv.mod_revision == revision
    assert read_revision >= revision


def test_prefix_is_ordered_and_bounded(etcd: EtcdClient, etcd_prefix: bytes) -> None:
    for name in (b"c", b"a", b"b"):
        etcd.put(etcd_prefix + b"dir/" + name, name)
    etcd.put(etcd_prefix + b"dir0", b"fuera del prefijo")
    kvs, _ = etcd.get_prefix(etcd_prefix + b"dir/")
    assert [kv.value for kv in kvs] == [b"a", b"b", b"c"]
    assert etcd.count_prefix(etcd_prefix + b"dir/") == 3
    assert len(etcd.get_prefix(etcd_prefix + b"dir/", limit=1)[0]) == 1


def test_read_at_old_revision(etcd: EtcdClient, etcd_prefix: bytes) -> None:
    key = etcd_prefix + b"clave"
    first = etcd.put(key, b"uno")
    etcd.put(key, b"dos")
    kv, _ = etcd.get(key, revision=first)
    assert kv is not None and kv.value == b"uno"


def test_txn_applies_only_if_compares_hold(etcd: EtcdClient, etcd_prefix: bytes) -> None:
    key = etcd_prefix + b"clave"
    created = etcd.txn([compare_absent(key)], [op_put(key, b"uno")])
    assert created.succeeded
    repeated = etcd.txn([compare_absent(key)], [op_put(key, b"otro")], [op_get(key)])
    assert not repeated.succeeded
    assert repeated.responses[0].response_range.kvs[0].value == b"uno"
    kv, _ = etcd.get(key)
    assert kv is not None
    stale = etcd.txn([compare_mod_revision(key, kv.mod_revision - 1)], [op_put(key, b"dos")])
    assert not stale.succeeded
    current = etcd.txn([compare_mod_revision(key, kv.mod_revision)], [op_put(key, b"dos")])
    assert current.succeeded


def test_txn_deletes_a_whole_prefix(etcd: EtcdClient, etcd_prefix: bytes) -> None:
    for index in range(200):  # más que las 128 operaciones por transacción
        etcd.put(etcd_prefix + b"pending/" + str(index).encode(), b"x")
    response = etcd.txn([], [op_delete_prefix(etcd_prefix + b"pending/")])
    assert response.responses[0].response_delete_range.deleted == 200


def test_lease_keeps_and_removes_keys(etcd: EtcdClient, etcd_prefix: bytes) -> None:
    lease_id = etcd.grant_lease(5)
    key = etcd_prefix + b"con-arrendamiento"
    etcd.put(key, b"x", lease_id=lease_id)
    assert etcd.refresh_lease(lease_id) == 5
    etcd.revoke_lease(lease_id)
    assert etcd.get(key)[0] is None
    assert etcd.refresh_lease(lease_id) == 0


def test_switches_to_next_member(etcd_addr: str, etcd_prefix: bytes) -> None:
    with socket.socket() as probe:
        probe.bind(("localhost", 0))
        dead_addr = f"localhost:{probe.getsockname()[1]}"
    client = EtcdClient([dead_addr, etcd_addr], timeout_s=1)
    try:
        client.put(etcd_prefix + b"clave", b"x")
        assert client.get(etcd_prefix + b"clave")[0] is not None
    finally:
        client.close()
