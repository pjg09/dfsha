"""Escenario 4 (§11.4): el cliente solo conoce los servidores de metadatos y descubre lo demás.

Se ejecuta en client-1 con DFSHA_* en el entorno: python -c <script>.
"""

from pathlib import Path

from dfsha.client.client import DfshaClient, load_settings
from dfsha.common import config
from dfsha.common.errors import DfshaError
from dfsha.common.tls import load_identity, make_channel_factory
from dfsha.v1 import common_pb2, metadata_pb2, metadata_pb2_grpc

settings = load_settings()
create_channel = make_channel_factory(load_identity(settings.secrets_directory))
print("1. Cada servidor de metadatos, preguntado directamente:")
for addr in config.get_addrs("METADATA_ADDRS"):
    stub = metadata_pb2_grpc.MetadataServiceStub(create_channel(addr))
    request = metadata_pb2.AuthenticateRequest(username=settings.username, password=settings.password)
    try:
        stub.Authenticate(request, timeout=5)
        print(f"   {addr}: responde, es el líder")
    except Exception as error:  # noqa: BLE001
        failure = DfshaError.from_rpc_error(error)  # type: ignore[arg-type]
        print(f"   {addr}: {failure.code.name} [{failure.reason}], leader_addr = {failure.metadata.get('leader_addr')}")

print("\n2. El cliente empieza por un seguidor si es el primero de la lista: sigue la redirección y lo recuerda")
client = DfshaClient(settings)
print(f"   ls / -> {[entry.name for entry in client.list_directory('/')]}")
print(f"   líder recordado por el cliente: {client.metadata._leader_addr}")

print("\n3. Ubicaciones de /grande.bin (bloques 0 a 4): nombres de nodos, nunca IP")
with client.open("/grande.bin") as handle:
    request = metadata_pb2.GetBlockLocationsRequest(
        file_handle=handle._opened.file_handle, block_range=common_pb2.BlockRange(first_block_index=0, block_count=5)
    )
    for location in client.metadata.call_rpc("GetBlockLocations", request).locations:
        print(f"   bloque {location.block_index}: {', '.join(location.datanode_addrs)}")
client.close()
