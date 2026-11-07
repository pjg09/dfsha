"""Arranque del servidor de metadatos: configuración, cliente de etcd, elección del líder y servidor gRPC."""

import logging
import signal
import threading
from concurrent import futures
from dataclasses import dataclass

import grpc

from dfsha.common import config
from dfsha.common.log import configure_logging
from dfsha.metadata.etcd_client import EtcdClient
from dfsha.metadata.keys import Keys
from dfsha.metadata.leader import LeaderElection
from dfsha.metadata.nodes import NodeRegistry
from dfsha.metadata.service import MetadataService, MetadataSettings
from dfsha.metadata.store import MetadataStore
from dfsha.v1 import metadata_pb2_grpc

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MetadataConfig:
    settings: MetadataSettings
    etcd_addrs: list[str]
    key_prefix: bytes
    leader_ttl_s: int
    leader_refresh_interval_s: float
    leader_step_down_after_s: float
    suspect_after_s: float
    dead_after_s: float
    server_threads: int
    log_level: str


def load_config() -> MetadataConfig:
    """Lee la configuración de las variables DFSHA_* (convenciones §2)."""
    settings = MetadataSettings(
        addr=config.get_addr("METADATA_ADDR"),
        block_size_bytes=config.get_int("BLOCK_SIZE_BYTES", 16 * 1024 * 1024),
        replication_factor=config.get_int("REPLICATION_FACTOR", 3),
        write_quorum=config.get_int("WRITE_QUORUM", 2),
        lease_ttl_s=config.get_int("LEASE_TTL_S", 30),
        grace_period_s=config.get_int("GRACE_PERIOD_S", 600),
        request_ttl_s=config.get_int("REQUEST_TTL_S", 600),
    )
    return MetadataConfig(
        settings=settings,
        etcd_addrs=config.get_addrs("ETCD_ADDRS"),
        key_prefix=config.get_str("KEY_PREFIX", "/dfsha/").encode(),
        leader_ttl_s=config.get_int("LEADER_TTL_S", 5),
        leader_refresh_interval_s=config.get_float("LEADER_REFRESH_INTERVAL_S", 1.0),
        leader_step_down_after_s=config.get_float("LEADER_STEP_DOWN_AFTER_S", 3.5),
        suspect_after_s=config.get_float("SUSPECT_AFTER_S", 9.0),
        dead_after_s=config.get_float("DEAD_AFTER_S", 30.0),
        server_threads=config.get_int("SERVER_THREADS", 16),
        log_level=config.get_str("LOG_LEVEL", "INFO"),
    )


@dataclass
class MetadataServer:
    server: grpc.Server
    port: int
    service: MetadataService
    election: LeaderElection
    etcd: EtcdClient

    def start(self) -> None:
        self.server.start()
        self.election.start()

    def stop(self, resign: bool = True) -> None:
        """Para el servidor. Sin ``resign`` simula una caída: el relevo espera a que caduque el arrendamiento."""
        self.election.stop(resign=resign)
        self.server.stop(grace=None)
        self.etcd.close()


def create_server(metadata_config: MetadataConfig) -> MetadataServer:
    etcd = EtcdClient(metadata_config.etcd_addrs)
    keys = Keys(metadata_config.key_prefix)
    registry = NodeRegistry(metadata_config.suspect_after_s, metadata_config.dead_after_s)
    service_holder: list[MetadataService] = []
    election = LeaderElection(
        etcd,
        keys.leader,
        metadata_config.settings.addr,
        metadata_config.leader_ttl_s,
        metadata_config.leader_refresh_interval_s,
        metadata_config.leader_step_down_after_s,
        on_elected=lambda epoch: service_holder[0].on_elected(epoch),
    )
    service = MetadataService(metadata_config.settings, MetadataStore(etcd, keys), election, registry)
    service_holder.append(service)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=metadata_config.server_threads))
    metadata_pb2_grpc.add_MetadataServiceServicer_to_server(service, server)
    _, port = config.parse_addr(metadata_config.settings.addr)
    bound_port = server.add_insecure_port(f"[::]:{port}")  # TLS en la etapa 6 (ADR 0023)
    return MetadataServer(server, bound_port, service, election, etcd)


def main() -> None:
    metadata_config = load_config()
    configure_logging(metadata_config.log_level)
    metadata_server = create_server(metadata_config)
    metadata_server.start()
    logger.info("Servidor de metadatos escuchando en el puerto %d", metadata_server.port)
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    stopped.wait()
    logger.info("Parando el servidor de metadatos")
    metadata_server.stop()
