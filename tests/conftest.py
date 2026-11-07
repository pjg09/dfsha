"""Fixtures comunes: un etcd v3.7.3 real para las pruebas del servidor de metadatos (ADR 0041)."""

import os
import shutil
import subprocess
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from dfsha.common import pki
from dfsha.metadata.etcd_client import EtcdClient, EtcdError

# La misma versión y digest que el despliegue (ADR 0040)
ETCD_IMAGE = "gcr.io/etcd-development/etcd:v3.7.3@sha256:0d27b9478551f431f82d1e0ddb6c87ad07ebae8b904c637f3a99213349523910"


def _wait_for_etcd(addr: str, timeout_s: float = 20) -> None:
    client = EtcdClient([addr], timeout_s=1)
    deadline = time.monotonic() + timeout_s
    try:
        while True:
            try:
                client.get(b"/ping")
                return
            except EtcdError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.2)
    finally:
        client.close()


@pytest.fixture(scope="session")
def etcd_addr() -> Iterator[str]:
    """Dirección de un etcd para las pruebas.

    Usa DFSHA_TEST_ETCD_ADDR si está definida (así lo hace GitHub Actions). Si no, arranca un
    contenedor de etcd con Docker; sin Docker, las pruebas que lo necesitan se saltan.
    """
    addr = os.environ.get("DFSHA_TEST_ETCD_ADDR")
    if addr:
        _wait_for_etcd(addr)
        yield addr
        return
    if shutil.which("docker") is None:
        pytest.skip("Sin etcd: define DFSHA_TEST_ETCD_ADDR o instala Docker")
    container = subprocess.run(
        ["docker", "run", "-d", "--rm", "-p", "2379", ETCD_IMAGE, "etcd",
         "--listen-client-urls", "http://[::]:2379", "--advertise-client-urls", "http://localhost:2379"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    if container.returncode != 0:
        pytest.skip(f"No se pudo arrancar etcd con Docker: {container.stderr.strip()}")
    container_id = container.stdout.strip()
    try:
        mapping = subprocess.run(
            ["docker", "port", container_id, "2379/tcp"], capture_output=True, text=True, check=True
        ).stdout.splitlines()[0]
        addr = f"localhost:{mapping.rsplit(':', 1)[1]}"
        _wait_for_etcd(addr)
        yield addr
    finally:
        subprocess.run(["docker", "rm", "-f", container_id], capture_output=True, check=False)


@pytest.fixture
def etcd_prefix() -> bytes:
    """Prefijo de claves propio de cada prueba, para que no se pisen entre sí."""
    return f"/test-{uuid.uuid4().hex}/".encode()


@pytest.fixture
def etcd(etcd_addr: str) -> Iterator[EtcdClient]:
    client = EtcdClient([etcd_addr])
    yield client
    client.close()


@pytest.fixture(scope="session")
def cluster_secrets(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Secretos de un clúster de prueba: CA interna, certificados con localhost en el SAN y claves (§10.7)."""
    directory = tmp_path_factory.mktemp("secretos")
    hosts = [f"metadata-{n}" for n in (1, 2, 3)] + [f"datanode-{n}" for n in range(1, 6)] + ["client-1", "client-2"]
    pki.create_cluster_secrets(directory, hosts, extra_names=["localhost"])
    return directory

