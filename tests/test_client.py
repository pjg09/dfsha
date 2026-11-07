"""Cliente (biblioteca y línea de órdenes) contra un clúster real en localhost sobre etcd real."""

import gc
import hashlib
import io
import logging
import os
import tracemalloc
from collections.abc import Callable, Iterator
from pathlib import Path

import grpc
import pytest
from helpers import wait_until
from local_cluster import BLOCK_SIZE_BYTES, LocalCluster

from dfsha.client.cli import main, resolve_path
from dfsha.client.client import ClientSettings, DfshaClient
from dfsha.client.connection import RetryPolicy
from dfsha.client.file_handle import FileHandle
from dfsha.common.errors import DfshaError, Reason
from dfsha.v1 import common_pb2, metadata_pb2


@pytest.fixture
def cluster(etcd_addr: str, etcd_prefix: bytes, tmp_path: Path, cluster_secrets: Path) -> Iterator[LocalCluster]:
    local = LocalCluster(etcd_addr, etcd_prefix, tmp_path, cluster_secrets, suspect_after_s=0.5)
    try:
        for _ in range(3):
            local.start_metadata()
        assert wait_until(lambda: sum(server.election.is_leader for server in local.metadata.values()) == 1)
        local.create_test_user()
        for index in range(1, 5):
            local.start_datanode(index)
        assert wait_until(lambda: all(d.metadata_client is not None and d.metadata_client.is_registered for d in local.datanodes))
        yield local
    finally:
        local.stop()


@pytest.fixture
def client(cluster: LocalCluster, cluster_secrets: Path) -> Iterator[DfshaClient]:
    # El primer servidor configurado es un seguidor: el cliente tiene que seguir la redirección
    follower = next(addr for addr, server in cluster.metadata.items() if not server.election.is_leader)
    addrs = [follower, *[addr for addr in cluster.metadata if addr != follower]]
    settings = ClientSettings(
        metadata_addrs=addrs, secrets_directory=cluster_secrets / "client-1", username=cluster.username,
        password=cluster.password, rpc_timeout_s=3, transfer_timeout_s=10, retry=RetryPolicy(max_total_s=30),
    )  # fmt: skip
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


def test_cli(
    cluster: LocalCluster, cluster_secrets: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DFSHA_METADATA_ADDRS", ",".join(cluster.metadata))
    monkeypatch.setenv("DFSHA_SECRETS_DIRECTORY", str(cluster_secrets / "client-1"))
    monkeypatch.setenv("DFSHA_USERNAME", cluster.username)
    monkeypatch.setenv("DFSHA_PASSWORD", cluster.password)
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


def test_blocks_on_disk_are_encrypted(cluster: LocalCluster, client: DfshaClient, tmp_path: Path) -> None:
    marker = b"TEXTO-EN-CLARO-QUE-NO-DEBE-VERSE "
    (tmp_path / "claro.txt").write_bytes(marker * 1000)
    client.put(tmp_path / "claro.txt", "/claro.txt")
    stored = [path.read_bytes() for path in tmp_path.glob("datanode-*/blocks/*/*") if not path.name.endswith(".meta")]
    assert stored, "no se encontraron bloques en disco"
    assert all(marker not in data for data in stored)  # ningún nodo de datos ve el texto en claro (§10.5)
    assert all(len(data) == len(marker) * 1000 + 28 for data in stored)  # nonce y etiqueta: 28 bytes más
    client.get("/claro.txt", tmp_path / "recuperado.txt")
    assert (tmp_path / "recuperado.txt").read_bytes() == marker * 1000


def test_cli_useradd_needs_an_admin(
    cluster: LocalCluster, cluster_secrets: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DFSHA_METADATA_ADDRS", ",".join(cluster.metadata))
    monkeypatch.setenv("DFSHA_SECRETS_DIRECTORY", str(cluster_secrets / "client-1"))
    monkeypatch.setenv("DFSHA_NEW_PASSWORD", "contraseña-nueva")
    monkeypatch.setenv("DFSHA_USERNAME", cluster.username)
    monkeypatch.setenv("DFSHA_PASSWORD", cluster.password)
    assert main(["useradd", "nueva"]) == 1  # el usuario de prueba no es administrador
    monkeypatch.setenv("DFSHA_USERNAME", "admin")
    monkeypatch.setenv("DFSHA_PASSWORD", (cluster_secrets / "admin-password").read_text().strip())
    assert main(["useradd", "nueva"]) == 0
    assert "Usuario nueva creado" in capsys.readouterr().out



def _cli_env(monkeypatch: pytest.MonkeyPatch, cluster: LocalCluster, cluster_secrets: Path) -> None:
    monkeypatch.setenv("DFSHA_METADATA_ADDRS", ",".join(cluster.metadata))
    monkeypatch.setenv("DFSHA_SECRETS_DIRECTORY", str(cluster_secrets / "client-1"))
    monkeypatch.setenv("DFSHA_USERNAME", cluster.username)
    monkeypatch.setenv("DFSHA_PASSWORD", cluster.password)


def test_cli_rf3_commands(
    cluster: LocalCluster, cluster_secrets: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _cli_env(monkeypatch, cluster, cluster_secrets)
    (tmp_path / "base.txt").write_bytes(b"0123456789")
    assert main(["put", str(tmp_path / "base.txt"), "/t.txt"]) == 0
    assert main(["write", "/t.txt", "2", "=AB"]) == 0  # modificación parcial con texto literal
    assert main(["append", "/t.txt", "=xyz"]) == 0
    assert main(["read", "/t.txt", "1", "20", str(tmp_path / "leido.txt")]) == 0
    assert (tmp_path / "leido.txt").read_bytes() == b"1AB456789xyz"
    assert "versión 3" in capsys.readouterr().out
    assert main(["write", "/no-existe.txt", "0", "=x"]) == 1
    assert "[PATH_NOT_FOUND]" in capsys.readouterr().err


def test_cli_shell_with_an_open_file(
    cluster: LocalCluster, cluster_secrets: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _cli_env(monkeypatch, cluster, cluster_secrets)
    session = "\n".join([
        "open /s.txt c", "write 0 =hola", "append =' mundo'", "close",
        "open /s.txt w", "lock 0 1", "write 0 =HOLA", f"read 0 20 {tmp_path / 'antes.txt'}", "close",
        "open /s.txt w", "write 0 =perdido",  # se sale sin cerrar: se descarta
    ])  # fmt: skip
    monkeypatch.setattr("sys.stdin", io.StringIO(session + "\n"))
    assert main(["shell"]) == 0
    captured = capsys.readouterr()
    assert "/s.txt: versión 1" in captured.out and "/s.txt: versión 2" in captured.out, captured.err
    assert "se descartan sus escrituras" in captured.err
    assert (tmp_path / "antes.txt").read_bytes() == b"HOLA mundo"  # lo propio se lee antes de cerrar
    assert main(["read", "/s.txt", "0", "20", str(tmp_path / "despues.txt")]) == 0
    assert (tmp_path / "despues.txt").read_bytes() == b"HOLA mundo"


def test_failed_replicas_do_not_retain_blocks(cluster: LocalCluster, client: DfshaClient, tmp_path: Path) -> None:
    # En AWS, un get de 1 GiB con un nodo de datos caído murió por falta de memoria (etapa 9): cada lectura
    # fallida dejaba un ciclo de referencias que retenía el bloque leído después, hasta el recolector cíclico
    data = _write(tmp_path / "origen.bin", 20 * BLOCK_SIZE_BYTES)
    client.put(tmp_path / "origen.bin", "/muchos.bin")
    cluster.datanodes[0].stop()  # parte de las réplicas fallan al leerlas
    gc.collect()
    gc.disable()  # solo se libera lo que libera el recuento de referencias
    tracemalloc.start()
    try:
        client.get("/muchos.bin", tmp_path / "copia.bin")
        retained, _ = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
        gc.enable()
    assert (tmp_path / "copia.bin").read_bytes() == data
    assert retained < 4 * BLOCK_SIZE_BYTES, f"quedan {retained / 2**20:.0f} MiB retenidos"


# ===== RF3: open, read, write, lock, unlock y close (§7) ======================================

B = BLOCK_SIZE_BYTES


def _check(client: DfshaClient, path: str, expected: bytearray) -> None:
    with client.open(path) as handle:
        assert handle.size == len(expected)
        assert handle.read(0, len(expected) + 10) == bytes(expected)


def test_rf3_write_modes_match_a_local_model(client: DfshaClient) -> None:
    model = bytearray()

    def write(path: str, mode: common_pb2.WriteMode | None, data: bytes, offset: int = 0) -> None:
        open_mode = metadata_pb2.OPEN_MODE_CREATE if mode == common_pb2.WRITE_MODE_CREATE else metadata_pb2.OPEN_MODE_WRITE
        with client.open(path, open_mode) as handle:
            handle.write(data, offset, mode)
        if mode in (common_pb2.WRITE_MODE_CREATE, common_pb2.WRITE_MODE_REPLACE):
            model[:] = b""
        if mode == common_pb2.WRITE_MODE_APPEND:
            offset = len(model)
        if offset > len(model):
            model.extend(bytes(offset - len(model)))
        model[offset : offset + len(data)] = data
        _check(client, path, model)

    write("/rf3.bin", common_pb2.WRITE_MODE_CREATE, os.urandom(2 * B + 300))
    write("/rf3.bin", common_pb2.WRITE_MODE_APPEND, os.urandom(B))  # completa el bloque 2 y crea el 3
    write("/rf3.bin", common_pb2.WRITE_MODE_PARTIAL, os.urandom(1000), B - 500)  # cruza los bloques 0 y 1
    write("/rf3.bin", common_pb2.WRITE_MODE_PARTIAL, b"cola", len(model) + B + 7)  # más allá del final: hueco con ceros
    write("/rf3.bin", common_pb2.WRITE_MODE_REPLACE, b"contenido nuevo y corto")
    write("/rf3.bin", common_pb2.WRITE_MODE_APPEND, b"")  # anexar nada no cambia el archivo
    assert client.get_file_info("/rf3.bin").version == 6


def test_rf3_reads_byte_ranges_and_own_writes(client: DfshaClient) -> None:
    data = os.urandom(3 * B)
    with client.open("/rango.bin", metadata_pb2.OPEN_MODE_CREATE) as handle:
        handle.write(data)
        assert handle.read(B - 3, 6) == data[B - 3 : B + 3]  # lo escrito se lee antes de cerrar
    with client.open("/rango.bin") as reader:
        assert reader.read(2 * B + 5, 10) == data[2 * B + 5 : 2 * B + 15]
        assert reader.read(3 * B, 10) == b""
        error = _expect(lambda: reader.write(b"x"))
        assert error.code == grpc.StatusCode.FAILED_PRECONDITION


def test_rf3_close_to_open_guarantees(client: DfshaClient) -> None:
    old, new = os.urandom(B + 10), os.urandom(B + 20)
    with client.open("/g.bin", metadata_pb2.OPEN_MODE_CREATE) as handle:
        handle.write(old)
    reader = client.open("/g.bin")
    with client.open("/g.bin", metadata_pb2.OPEN_MODE_WRITE) as writer:
        writer.write(new, 0, common_pb2.WRITE_MODE_REPLACE)
        with client.open("/g.bin") as during:
            assert during.read(0, len(new)) == old  # G4: lo no confirmado no se ve
    assert reader.read(0, len(old) + 50) == old  # G3: quien ya lo tenía abierto sigue con su versión
    reader.close()
    with client.open("/g.bin") as after:
        assert after.read(0, len(new) + 50) == new  # G2: un open() posterior ve la confirmada


def test_rf3_concurrent_writers(client: DfshaClient) -> None:
    data = bytearray(os.urandom(4 * B))
    with client.open("/c.bin", metadata_pb2.OPEN_MODE_CREATE) as handle:
        handle.write(bytes(data))
    first = client.open("/c.bin", metadata_pb2.OPEN_MODE_WRITE)
    second = client.open("/c.bin", metadata_pb2.OPEN_MODE_WRITE)
    first.write(b"A" * 10, 5, common_pb2.WRITE_MODE_PARTIAL)  # bloque 0
    error = _expect(lambda: second.write(b"B" * 10, 20, common_pb2.WRITE_MODE_PARTIAL))  # mismo bloque
    assert (error.code, error.reason) == (grpc.StatusCode.ABORTED, Reason.LOCK_CONFLICT)
    second.write(b"C" * 10, 3 * B, common_pb2.WRITE_MODE_PARTIAL)  # otro bloque: los dos escriben
    assert first.close() == 2
    assert second.close() == 3  # se aplica sobre la versión del primero (§8.2)
    data[5:15], data[3 * B : 3 * B + 10] = b"A" * 10, b"C" * 10
    _check(client, "/c.bin", data)


def test_rf3_scenario_1_same_block(client: DfshaClient) -> None:
    # Escenario 1 de §11.1, pasos 1 a 4: P1 y P2 abren la versión v y quieren modificar el bloque 3
    with client.open("/datos.bin", metadata_pb2.OPEN_MODE_CREATE) as handle:
        handle.write(os.urandom(4 * B))
    p1 = client.open("/datos.bin", metadata_pb2.OPEN_MODE_WRITE)
    p2 = client.open("/datos.bin", metadata_pb2.OPEN_MODE_WRITE)
    p1.write(b"P1", 3 * B)
    assert _expect(lambda: p2.write(b"P2", 3 * B)).reason == Reason.LOCK_CONFLICT  # al momento, sin esperar
    assert p1.close() == 2
    p2.write(b"P2", 3 * B)  # ahora obtiene el arrendamiento, pero sigue partiendo de la versión v
    error = _expect(p2.close)
    assert (error.code, error.reason) == (grpc.StatusCode.ABORTED, Reason.VERSION_CONFLICT)
    with client.open("/datos.bin", metadata_pb2.OPEN_MODE_WRITE) as again:  # vuelve a abrir v + 1
        assert again.read(3 * B, 2) == b"P1"
        again.write(b"P2", 3 * B + 2)
    with client.open("/datos.bin") as reader:
        assert reader.read(3 * B, 4) == b"P1P2"  # nunca una mezcla: cada cambio entero, uno detrás de otro


def test_rf3_lock_groups_writes_and_rejects_writes_outside_it(client: DfshaClient) -> None:
    with client.open("/l.bin", metadata_pb2.OPEN_MODE_CREATE) as handle:
        handle.write(os.urandom(3 * B))
    with client.open("/l.bin", metadata_pb2.OPEN_MODE_WRITE) as handle:
        handle.lock(0, 2)
        handle.write(b"x", 10, common_pb2.WRITE_MODE_PARTIAL)
        handle.write(b"y", B + 10)
        error = _expect(lambda: handle.write(b"z", 2 * B + 10))  # fuera del rango arrendado
        assert error.code == grpc.StatusCode.FAILED_PRECONDITION
        assert _expect(handle.unlock).code == grpc.StatusCode.FAILED_PRECONDITION  # hay escrituras sin confirmar
    with client.open("/l.bin") as reader:
        assert (reader.read(10, 1), reader.read(B + 10, 1)) == (b"x", b"y")


def test_rf3_writer_that_dies_loses_its_lease(
    etcd_addr: str, etcd_prefix: bytes, tmp_path: Path, cluster_secrets: Path
) -> None:
    # Escenario 1 de §11.1 con un TTL de 2 s en lugar de 30
    local = LocalCluster(etcd_addr, etcd_prefix, tmp_path, cluster_secrets, lease_ttl_s=2)
    try:
        for _ in range(3):
            local.start_metadata()
        assert wait_until(lambda: sum(server.election.is_leader for server in local.metadata.values()) == 1)
        local.create_test_user()
        for index in range(1, 4):
            local.start_datanode(index)
        assert wait_until(lambda: all(d.metadata_client is not None and d.metadata_client.is_registered for d in local.datanodes))
        settings = ClientSettings(
            metadata_addrs=list(local.metadata), secrets_directory=cluster_secrets / "client-1", username=local.username,
            password=local.password, rpc_timeout_s=3, transfer_timeout_s=10, retry=RetryPolicy(max_total_s=30),
        )  # fmt: skip
        with DfshaClient(settings) as client:
            with client.open("/d.bin", metadata_pb2.OPEN_MODE_CREATE) as handle:
                handle.write(os.urandom(100))
            dead = client.open("/d.bin", metadata_pb2.OPEN_MODE_WRITE)
            dead.write(b"muerto", 0, common_pb2.WRITE_MODE_PARTIAL)
            assert dead._keeper is not None
            dead._keeper.stop()  # el proceso deja de renovar, como si hubiera muerto
            alive = client.open("/d.bin", metadata_pb2.OPEN_MODE_WRITE)
            assert _expect(lambda: alive.write(b"vivo", 0, common_pb2.WRITE_MODE_PARTIAL)).reason == Reason.LOCK_CONFLICT
            assert wait_until(lambda: _try_write(alive, b"vivo"), timeout_s=10)  # caduca solo, sin intervención
            assert alive.close() == 2
            assert _expect(dead.close).reason == Reason.LEASE_EXPIRED  # el que reaparece no pisa al otro
            with client.open("/d.bin") as reader:
                assert reader.read(0, 4) == b"vivo"
    finally:
        local.stop()


def _try_write(handle: FileHandle, data: bytes) -> bool:
    try:
        handle.write(data, 0, common_pb2.WRITE_MODE_PARTIAL)
        return True
    except DfshaError as error:
        assert error.reason == Reason.LOCK_CONFLICT
        return False


def _expect(operation: Callable[[], object]) -> DfshaError:
    with pytest.raises(DfshaError) as caught:
        operation()
    return caught.value
