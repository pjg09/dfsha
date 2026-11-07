"""Cliente (biblioteca y línea de órdenes) contra un clúster real en localhost sobre etcd real."""

import hashlib
import logging
import os
from collections.abc import Iterator
from pathlib import Path

import grpc
import pytest
from helpers import wait_until
from local_cluster import BLOCK_SIZE_BYTES, LocalCluster

from dfsha.client.cli import main, resolve_path
from dfsha.client.client import ClientSettings, DfshaClient
from dfsha.client.connection import RetryPolicy
from dfsha.common.errors import DfshaError, Reason


@pytest.fixture
def cluster(etcd_addr: str, etcd_prefix: bytes, tmp_path: Path) -> Iterator[LocalCluster]:
    local = LocalCluster(etcd_addr, etcd_prefix, tmp_path, suspect_after_s=0.5)
    try:
        for _ in range(3):
            local.start_metadata()
        assert wait_until(lambda: sum(server.election.is_leader for server in local.metadata.values()) == 1)
        for index in range(1, 5):
            local.start_datanode(index)
        assert wait_until(lambda: all(d.metadata_client is not None and d.metadata_client.is_registered for d in local.datanodes))
        yield local
    finally:
        local.stop()


@pytest.fixture
def client(cluster: LocalCluster) -> Iterator[DfshaClient]:
    # El primer servidor configurado es un seguidor: el cliente tiene que seguir la redirección
    follower = next(addr for addr, server in cluster.metadata.items() if not server.election.is_leader)
    addrs = [follower, *[addr for addr in cluster.metadata if addr != follower]]
    settings = ClientSettings(metadata_addrs=addrs, rpc_timeout_s=3, transfer_timeout_s=10, retry=RetryPolicy(max_total_s=30))
    with DfshaClient(settings) as created:
        yield created


def _write(path: Path, size: int) -> bytes:
    data = os.urandom(size)
    path.write_bytes(data)
    return data


def test_resolve_path() -> None:
    assert resolve_path("/a/b", "c") == "/a/b/c"
    assert resolve_path("/a/b", "../c") == "/a/c"
    assert resolve_path("/a/b", "/x/./y/") == "/x/y"
    assert resolve_path("/", "..") == "/"


def test_put_and_get_several_blocks(client: DfshaClient, tmp_path: Path) -> None:
    data = _write(tmp_path / "origen.bin", 3 * BLOCK_SIZE_BYTES + 777)
    assert client.put(tmp_path / "origen.bin", "/datos.bin") == 1
    assert client.get("/datos.bin", tmp_path / "copia.bin") == len(data)
    assert hashlib.sha256((tmp_path / "copia.bin").read_bytes()).digest() == hashlib.sha256(data).digest()
    assert not (tmp_path / "copia.bin.dfsha-parcial").exists()


def test_empty_file(client: DfshaClient, tmp_path: Path) -> None:
    (tmp_path / "vacio").write_bytes(b"")
    client.put(tmp_path / "vacio", "/vacio")
    client.get("/vacio", tmp_path / "vacio-copia")
    assert (tmp_path / "vacio-copia").read_bytes() == b""


def test_put_again_replaces(client: DfshaClient, tmp_path: Path) -> None:
    _write(tmp_path / "v1", 1000)
    second = _write(tmp_path / "v2", BLOCK_SIZE_BYTES + 5)
    assert client.put(tmp_path / "v1", "/archivo") == 1
    assert client.put(tmp_path / "v2", "/archivo") == 2
    client.get("/archivo", tmp_path / "copia")
    assert (tmp_path / "copia").read_bytes() == second


def test_namespace_operations(client: DfshaClient, tmp_path: Path) -> None:
    client.create_directory("/docs")
    _write(tmp_path / "a", 10)
    client.put(tmp_path / "a", "/docs/a.txt")
    client.move("/docs/a.txt", "/docs/b.txt")
    assert [entry.name for entry in client.list_directory("/docs")] == ["b.txt"]
    assert client.get_file_info("/docs/b.txt").size_bytes == 10
    client.delete_file("/docs/b.txt")
    client.delete_directory("/docs")
    assert client.list_directory("/") == []


def test_errors_keep_their_reason(client: DfshaClient, tmp_path: Path) -> None:
    _write(tmp_path / "a", 10)
    with pytest.raises(DfshaError) as missing_parent:
        client.put(tmp_path / "a", "/no/existe")
    assert missing_parent.value.reason is Reason.PATH_NOT_FOUND
    with pytest.raises(DfshaError) as missing_file:
        client.get("/no-existe", tmp_path / "x")
    assert missing_file.value.code is grpc.StatusCode.NOT_FOUND
    assert not (tmp_path / "x").exists()


def test_put_survives_a_dead_secondary(cluster: LocalCluster, client: DfshaClient, tmp_path: Path) -> None:
    cluster.datanodes.pop().stop()  # cae un nodo de datos justo antes de la carga
    data = _write(tmp_path / "origen.bin", 4 * BLOCK_SIZE_BYTES)
    client.put(tmp_path / "origen.bin", "/datos.bin")  # como secundaria, W = 2 se alcanza sin él
    client.get("/datos.bin", tmp_path / "copia.bin")
    assert (tmp_path / "copia.bin").read_bytes() == data


def test_put_reallocates_blocks_on_dead_nodes(
    cluster: LocalCluster, client: DfshaClient, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Con 2 de 4 nodos caídos, cada bloque tiene al menos una réplica en un nodo muerto, y muchos la primaria
    # o dos réplicas: esos fallan y el cliente los repite en otros nodos con un block_id nuevo (§11.3)
    for _ in range(2):
        cluster.datanodes.pop().stop()
    data = _write(tmp_path / "origen.bin", 8 * BLOCK_SIZE_BYTES)
    with caplog.at_level(logging.WARNING, logger="dfsha.client.client"):
        client.put(tmp_path / "origen.bin", "/datos.bin")
    assert "se reserva de nuevo" in caplog.text
    client.get("/datos.bin", tmp_path / "copia.bin")
    assert (tmp_path / "copia.bin").read_bytes() == data


def test_client_rides_through_a_leader_crash(cluster: LocalCluster, client: DfshaClient, tmp_path: Path) -> None:
    data = _write(tmp_path / "antes", BLOCK_SIZE_BYTES + 3)
    client.put(tmp_path / "antes", "/antes")
    leader = cluster.get_leader()
    cluster.metadata.pop(leader).stop(resign=False)
    client.get("/antes", tmp_path / "copia")  # reintenta hasta que hay un líder nuevo
    assert (tmp_path / "copia").read_bytes() == data
    after = _write(tmp_path / "despues", 2000)
    client.put(tmp_path / "despues", "/despues")  # reintenta QUORUM_NOT_REACHED hasta los latidos
    client.get("/despues", tmp_path / "copia2")
    assert (tmp_path / "copia2").read_bytes() == after


def test_cli(cluster: LocalCluster, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("DFSHA_METADATA_ADDRS", ",".join(cluster.metadata))
    _write(tmp_path / "a.bin", 1234)
    assert main(["mkdir", "/docs"]) == 0
    assert main(["put", str(tmp_path / "a.bin"), "/docs/a.bin"]) == 0
    assert main(["ls", "/docs"]) == 0
    assert main(["get", "/docs/a.bin", str(tmp_path / "b.bin")]) == 0
    output = capsys.readouterr().out
    assert "a.bin" in output and "versión 1" in output
    assert (tmp_path / "b.bin").read_bytes() == (tmp_path / "a.bin").read_bytes()
    assert main(["rmdir", "/docs"]) == 1
    assert "[DIRECTORY_NOT_EMPTY]" in capsys.readouterr().err
