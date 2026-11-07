"""Llamadas que el clúster tiene que rechazar. Se ejecuta dentro del contenedor client-1:
python - <block_id> < sondas.py. Usa el certificado de client-1 salvo donde se indica."""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import grpc

from dfsha.common.errors import DfshaError
from dfsha.common.tls import load_identity, make_channel_factory
from dfsha.v1 import common_pb2, datanode_pb2, datanode_pb2_grpc, metadata_pb2, metadata_pb2_grpc

block_id = sys.argv[1]
identity = load_identity(Path("/run/secrets/dfsha"))
create_channel = make_channel_factory(identity)


def probe(label, call):
    try:
        call()
        print(f"{label}: ACEPTADA")
    except grpc.RpcError as error:
        failure = DfshaError.from_rpc_error(error)
        reason = f" [{failure.reason}]" if failure.reason else ""
        print(f"{label}: rechazada, {failure.code.name}{reason}: {failure.message}")


listing = metadata_pb2.ListDirectoryRequest(path="/")
plain = metadata_pb2_grpc.MetadataServiceStub(grpc.insecure_channel("metadata-1:50051"))
probe("ListDirectory en texto plano, sin TLS", lambda: plain.ListDirectory(listing, timeout=5))

no_cert = grpc.secure_channel("metadata-1:50051", grpc.ssl_channel_credentials(root_certificates=identity.ca_cert))
probe("ListDirectory con TLS pero sin certificado de cliente",
      lambda: metadata_pb2_grpc.MetadataServiceStub(no_cert).ListDirectory(listing, timeout=5))

metadata = metadata_pb2_grpc.MetadataServiceStub(create_channel("metadata-1:50051"))
probe("ListDirectory con certificado y sin token de acceso", lambda: metadata.ListDirectory(listing, timeout=5))
probe("ListDirectory con un token de acceso inventado",
      lambda: metadata.ListDirectory(listing, timeout=5, metadata=[("authorization", "Bearer AAAA.inventado")]))
probe("RegisterDataNode como datanode-1 con el certificado de client-1",
      lambda: metadata.RegisterDataNode(metadata_pb2.RegisterDataNodeRequest(
          node_id="datanode-1", hostname="datanode-1", capacity_bytes=1, free_bytes=1), timeout=5))

datanode = datanode_pb2_grpc.DataNodeServiceStub(create_channel("datanode-1:50052"))
probe("ReadBlock de una réplica existente sin token de bloque",
      lambda: list(datanode.ReadBlock(datanode_pb2.ReadBlockRequest(block_id=block_id), timeout=5)))
expires_at = datetime.now(UTC) + timedelta(minutes=5)
forged = common_pb2.BlockToken(block_id=block_id, operation=common_pb2.BLOCK_OPERATION_READ, signature=b"\0" * 32)
forged.expires_at.FromDatetime(expires_at)
probe("ReadBlock con un token de bloque de firma inventada",
      lambda: list(datanode.ReadBlock(datanode_pb2.ReadBlockRequest(block_id=block_id, block_token=forged), timeout=5)))
