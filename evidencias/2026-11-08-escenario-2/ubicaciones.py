"""Ubicaciones que anuncia el servidor de metadatos para cada bloque de la versión vigente de un archivo.

Se ejecuta en client-1 con DFSHA_* en el entorno: python -c <script> <ruta>.
"""

import sys

from dfsha.client.client import DfshaClient, load_settings
from dfsha.v1 import common_pb2, metadata_pb2

client = DfshaClient(load_settings())
with client.open(sys.argv[1]) as handle:
    request = metadata_pb2.GetBlockLocationsRequest(file_handle=handle._opened.file_handle, block_range=common_pb2.BlockRange())
    locations = client.metadata.call_rpc("GetBlockLocations", request).locations
    print(f"{sys.argv[1]} versión {handle.version}:")
    for location in locations:
        names = sorted(addr.split(":")[0] for addr in location.datanode_addrs)
        print(f"  bloque {location.block_index}: {len(names)} réplicas en {', '.join(names)}")
client.close()
