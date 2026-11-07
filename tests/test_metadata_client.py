"""Bucle de latidos del nodo de datos frente a errores inesperados del líder."""

import time
from pathlib import Path

import grpc

from dfsha.common.errors import DfshaError
from dfsha.datanode.block_store import BlockStore, initialize_data_directory
from dfsha.datanode.metadata_client import MetadataClient


def test_heartbeat_loop_survives_unexpected_errors(tmp_path: Path) -> None:
    # En AWS, un líder que se paraba respondió UNKNOWN a ReportBlocks y el hilo de latidos murió (etapa 7)
    initialize_data_directory(tmp_path, "datanode-1")
    client = MetadataClient(
        ["metadata-1:50051"], "datanode-1", "datanode-1:50052", BlockStore(tmp_path),
        heartbeat_interval_s=0.05, retry_interval_s=0.05,
    )
    calls: list[int] = []

    def register() -> None:
        calls.append(1)
        if len(calls) == 1:
            raise DfshaError(grpc.StatusCode.UNKNOWN, "Exception calling application")
        if len(calls) == 2:
            raise ValueError("fallo inesperado")

    client.register = register  # type: ignore[method-assign]
    client.start()
    try:
        deadline = time.monotonic() + 5
        while len(calls) < 3 and time.monotonic() < deadline:
            time.sleep(0.01)
    finally:
        client.stop()
    assert len(calls) >= 3
