"""Arranque del nodo de datos: configuración, comprobaciones del volumen y servidor gRPC."""

import logging
import signal
import threading
from concurrent import futures
from dataclasses import dataclass, field
from pathlib import Path

import grpc

from dfsha.common import config
from dfsha.common.log import configure_logging
from dfsha.common.pki import BLOCK_TOKEN_KEY_FILE
from dfsha.common.tls import DEFAULT_SECRETS_DIRECTORY, get_server_credentials, load_identity, make_channel_factory, read_secret
from dfsha.datanode.block_store import BlockStore, initialize_data_directory, verify_data_directory
from dfsha.datanode.metadata_client import MetadataClient
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
    secrets_directory: Path
    metadata_addrs: list[str] = field(default_factory=list)  # vacía: sin servidor de metadatos (pruebas)
    heartbeat_interval_s: float = 3.0
    block_report_interval_s: float = 300.0


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
        secrets_directory=Path(config.get_str("SECRETS_DIRECTORY", DEFAULT_SECRETS_DIRECTORY)),
        server_threads=config.get_int("SERVER_THREADS", 16),
        log_level=config.get_str("LOG_LEVEL", "INFO"),
        metadata_addrs=config.get_addrs("METADATA_ADDRS"),
        heartbeat_interval_s=config.get_float("HEARTBEAT_INTERVAL_S", 3.0),
        block_report_interval_s=config.get_float("BLOCK_REPORT_INTERVAL_S", 300.0),
    )


@dataclass
class DataNodeServer:
    server: grpc.Server
    port: int
    metadata_client: MetadataClient | None

    def start(self) -> None:
        self.server.start()
        if self.metadata_client is not None:
            self.metadata_client.start()

    def stop(self, grace_s: float | None = None) -> None:
        if self.metadata_client is not None:
            self.metadata_client.stop()
        self.server.stop(grace=grace_s).wait()


def create_server(
    node_config: DataNodeConfig, reporter: BlockReporter | None = None, channels: ChannelPool | None = None
) -> DataNodeServer:
    """Prepara el almacén, la relación con el líder de metadatos y el servidor gRPC, sin arrancarlos."""
    if node_config.initialize_data_directory:
        initialize_data_directory(node_config.data_directory, node_config.settings.node_id)
    verify_data_directory(node_config.data_directory, node_config.settings.node_id, node_config.require_mount_point)
    store = BlockStore(node_config.data_directory)
    store.clean_staging_area()
    identity = load_identity(node_config.secrets_directory)
    create_channel = make_channel_factory(identity)  # TLS mutuo con el certificado del nodo (ADR 0043)
    metadata_client = None
    if reporter is None and node_config.metadata_addrs:
        metadata_client = MetadataClient(
            node_config.metadata_addrs,
            node_config.settings.node_id,
            node_config.settings.addr,
            store,
            node_config.heartbeat_interval_s,
            block_report_interval_s=node_config.block_report_interval_s,
            create_channel=create_channel,
        )
        reporter = metadata_client
    service = DataNodeService(
        node_config.settings,
        store,
        reporter or LoggingBlockReporter(),
        channels or ChannelPool(create_channel),
        read_secret(node_config.secrets_directory, BLOCK_TOKEN_KEY_FILE),
    )
    options = [
        ("grpc.max_receive_message_length", MAX_MESSAGE_BYTES),
        ("grpc.max_send_message_length", MAX_MESSAGE_BYTES),
    ]
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=node_config.server_threads), options=options)
    datanode_pb2_grpc.add_DataNodeServiceServicer_to_server(service, server)
    _, port = config.parse_addr(node_config.settings.addr)
    bound_port = server.add_secure_port(f"[::]:{port}", get_server_credentials(identity))  # TLS mutuo (ADR 0043)
    return DataNodeServer(server, bound_port, metadata_client)


def main() -> None:
    node_config = load_config()
    configure_logging(node_config.log_level, node_config.settings.node_id)
    datanode_server = create_server(node_config)
    datanode_server.start()
    logger.info("Nodo de datos %s escuchando en el puerto %d", node_config.settings.node_id, datanode_server.port)
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    stopped.wait()
    logger.info("Parando el nodo de datos")
    datanode_server.stop(grace_s=5)
