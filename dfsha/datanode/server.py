"""Arranque del nodo de datos: configuración, comprobaciones del volumen y servidor gRPC."""

import logging
import signal
import threading
from concurrent import futures
from dataclasses import dataclass
from pathlib import Path

import grpc

from dfsha.common import config
from dfsha.common.log import configure_logging
from dfsha.datanode.block_store import BlockStore, initialize_data_directory, verify_data_directory
from dfsha.datanode.service import BlockReporter, ChannelPool, DataNodeService, DataNodeSettings, LoggingBlockReporter
from dfsha.v1 import datanode_pb2_grpc

logger = logging.getLogger(__name__)

MAX_MESSAGE_BYTES = 4 * 1024 * 1024  # holgura sobre los mensajes de 1 MiB


@dataclass(frozen=True)
class DataNodeConfig:
    settings: DataNodeSettings
    data_directory: Path
    require_mount_point: bool
    initialize_data_directory: bool
    server_threads: int
    log_level: str


def load_config() -> DataNodeConfig:
    """Lee la configuración de las variables DFSHA_* (convenciones §2)."""
    addr = config.get_addr("DATANODE_ADDR")
    settings = DataNodeSettings(
        node_id=config.get_str("NODE_ID"),
        addr=addr,
        block_size_bytes=config.get_int("BLOCK_SIZE_BYTES", 16 * 1024 * 1024),
        write_quorum=config.get_int("WRITE_QUORUM", 2),
        transfer_timeout_s=config.get_float("TRANSFER_TIMEOUT_S", 60.0),
    )
    return DataNodeConfig(
        settings=settings,
        data_directory=Path(config.get_str("DATA_DIRECTORY", "/data")),
        require_mount_point=config.get_bool("REQUIRE_MOUNT_POINT", True),
        initialize_data_directory=config.get_bool("INITIALIZE_DATA_DIRECTORY", False),
        server_threads=config.get_int("SERVER_THREADS", 16),
        log_level=config.get_str("LOG_LEVEL", "INFO"),
    )


def create_server(
    node_config: DataNodeConfig, reporter: BlockReporter | None = None, channels: ChannelPool | None = None
) -> tuple[grpc.Server, int]:
    """Prepara el almacén y el servidor gRPC. Devuelve el servidor sin arrancar y su puerto."""
    if node_config.initialize_data_directory:
        initialize_data_directory(node_config.data_directory, node_config.settings.node_id)
    verify_data_directory(node_config.data_directory, node_config.settings.node_id, node_config.require_mount_point)
    store = BlockStore(node_config.data_directory)
    store.clean_staging_area()
    service = DataNodeService(
        node_config.settings, store, reporter or LoggingBlockReporter(), channels or ChannelPool()
    )
    options = [
        ("grpc.max_receive_message_length", MAX_MESSAGE_BYTES),
        ("grpc.max_send_message_length", MAX_MESSAGE_BYTES),
    ]
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=node_config.server_threads), options=options)
    datanode_pb2_grpc.add_DataNodeServiceServicer_to_server(service, server)
    _, port = config.parse_addr(node_config.settings.addr)
    bound_port = server.add_insecure_port(f"[::]:{port}")  # TLS en la etapa 6 (ADR 0023)
    return server, bound_port


def main() -> None:
    node_config = load_config()
    configure_logging(node_config.log_level, node_config.settings.node_id)
    server, port = create_server(node_config)
    server.start()
    logger.info("Nodo de datos %s escuchando en el puerto %d", node_config.settings.node_id, port)
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    stopped.wait()
    logger.info("Parando el nodo de datos")
    server.stop(grace=5).wait()
