"""Cliente de etcd contra un etcd v3.7.3 real: lecturas, transacciones y arrendamientos (ADR 0041)."""

import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import ETCD_IMAGE

from dfsha.common.tls import load_identity, make_channel_factory

from dfsha.metadata.etcd_client import (
    EtcdClient,
    EtcdError,
    compare_absent,
    compare_mod_revision,
    compare_prefix_empty,
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


def test_compare_on_an_empty_prefix(etcd: EtcdClient, etcd_prefix: bytes) -> None:
    # Base de rmdir: comprobar que un directorio está vacío en la misma transacción que lo borra
    directory = etcd_prefix + b"entries/dir/"
    assert etcd.txn([compare_prefix_empty(directory)], []).succeeded
    etcd.put(directory + b"hijo", b"x")
    assert not etcd.txn([compare_prefix_empty(directory)], []).succeeded


@pytest.fixture
def tls_etcd_addr(cluster_secrets: Path) -> Iterator[str]:
    """Un etcd con TLS mutuo, como en producción (ADR 0039): certificado de metadata-1 y CA interna."""
    if shutil.which("docker") is None:
        pytest.skip("Hace falta Docker para arrancar un etcd con TLS")
    certs = cluster_secrets / "metadata-1"
    container = subprocess.run(
        ["docker", "run", "-d", "--rm", "-p", "2379", "-v", f"{certs}:/certs:ro", ETCD_IMAGE, "etcd",
         "--listen-client-urls", "https://[::]:2379", "--advertise-client-urls", "https://localhost:2379",
         "--cert-file", "/certs/cert.pem", "--key-file", "/certs/key.pem",
         "--trusted-ca-file", "/certs/ca.pem", "--client-cert-auth"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    if container.returncode != 0:
        pytest.skip(f"No se pudo arrancar etcd con TLS: {container.stderr.strip()}")
    container_id = container.stdout.strip()
    try:
        mapping = subprocess.run(["docker", "port", container_id, "2379/tcp"], capture_output=True, text=True, check=True)
        yield f"localhost:{mapping.stdout.splitlines()[0].rsplit(':', 1)[1]}"
    finally:
        subprocess.run(["docker", "rm", "-f", container_id], capture_output=True, check=False)


def test_etcd_with_mutual_tls(tls_etcd_addr: str, cluster_secrets: Path, etcd_prefix: bytes) -> None:
    secure = EtcdClient([tls_etcd_addr], timeout_s=2, create_channel=make_channel_factory(load_identity(cluster_secrets / "metadata-2")))
    try:
        deadline = time.monotonic() + 20
        while True:  # etcd tarda un momento en arrancar
            try:
                secure.put(etcd_prefix + b"clave", b"con TLS mutuo")
                break
            except EtcdError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.2)
        kv, _ = secure.get(etcd_prefix + b"clave")
        assert kv is not None and kv.value == b"con TLS mutuo"
    finally:
        secure.close()
    plaintext = EtcdClient([tls_etcd_addr], timeout_s=1)
    try:
        with pytest.raises(EtcdError):
            plaintext.get(etcd_prefix + b"clave")  # sin TLS no hay conexión
    finally:
        plaintext.close()
