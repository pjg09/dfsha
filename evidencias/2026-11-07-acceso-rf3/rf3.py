"""Acceso RF3 con la biblioteca del cliente, en client-1 y con bloques reales de 16 MiB (fase I §7).

Cada escritura se aplica también a un modelo local; después se lee el archivo entero y se compara su SHA-256
con el del modelo. Se listan los block_id de cada versión para ver qué bloques son nuevos (copia en
escritura, Tabla 22). Se ejecuta con DFSHA_* en el entorno: python -c <script>.
"""

import hashlib
import os

from dfsha.client.client import DfshaClient, load_settings
from dfsha.common.errors import DfshaError
from dfsha.v1 import common_pb2, metadata_pb2

PATH = "/rf3.bin"
client = DfshaClient(load_settings())
B = 0
model = bytearray()
MODES = {
    common_pb2.WRITE_MODE_CREATE: "creación", common_pb2.WRITE_MODE_REPLACE: "reemplazo",
    common_pb2.WRITE_MODE_APPEND: "anexado", common_pb2.WRITE_MODE_PARTIAL: "modificación parcial",
}  # fmt: skip


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def block_ids() -> list[str]:
    with client.open(PATH) as handle:
        request = metadata_pb2.GetBlockLocationsRequest(file_handle=handle._opened.file_handle, block_range=common_pb2.BlockRange())
        return [location.block_id[:8] for location in client.metadata.call_rpc("GetBlockLocations", request).locations]


def write(mode: int, data: bytes, offset: int = 0) -> None:
    before = block_ids() if mode != common_pb2.WRITE_MODE_CREATE else []
    open_mode = metadata_pb2.OPEN_MODE_CREATE if mode == common_pb2.WRITE_MODE_CREATE else metadata_pb2.OPEN_MODE_WRITE
    with client.open(PATH, open_mode) as handle:
        handle.write(data, offset, mode)
    if mode in (common_pb2.WRITE_MODE_CREATE, common_pb2.WRITE_MODE_REPLACE):
        model[:] = b""
    if mode == common_pb2.WRITE_MODE_APPEND:
        offset = len(model)
    if offset > len(model):
        model.extend(bytes(offset - len(model)))
    model[offset : offset + len(data)] = data
    after = block_ids()
    with client.open(PATH) as reader:
        content = reader.read(0, reader.size + 1)
        version, size = reader.version, reader.size
    reused = [index for index, block_id in enumerate(after) if index < len(before) and before[index] == block_id]
    print(f"\n{MODES[mode]}: offset {offset}, {len(data)} bytes")
    print(f"  versión {version}, {size} bytes, {len(after)} bloques")
    print(f"  bloques nuevos: {[i for i in range(len(after)) if i not in reused]}; reutilizados: {reused}")
    print(f"  SHA-256 leído {sha(content)} · modelo {sha(bytes(model))} · {'coincide' if content == model else 'NO COINCIDE'}")


try:
    client.delete_file(PATH)
except DfshaError:
    pass
probe = client.open("/grande.bin")
B = probe.block_size
probe.close()
print(f"Tamaño de bloque: {B} bytes")

write(common_pb2.WRITE_MODE_CREATE, os.urandom(2 * B + 300))
write(common_pb2.WRITE_MODE_APPEND, os.urandom(B))  # completa el bloque 2 y crea el 3
write(common_pb2.WRITE_MODE_PARTIAL, os.urandom(1000), B - 500)  # cruza los bloques 0 y 1
write(common_pb2.WRITE_MODE_PARTIAL, b"cola", len(model) + B + 7)  # más allá del final: hueco con ceros
write(common_pb2.WRITE_MODE_REPLACE, b"contenido nuevo y corto")

print("\nGarantías de consistencia (Tabla 23)")
old, new = os.urandom(B + 10), os.urandom(B + 20)
write(common_pb2.WRITE_MODE_REPLACE, old)
reader = client.open(PATH)
with client.open(PATH, metadata_pb2.OPEN_MODE_WRITE) as writer:
    writer.write(new, 0, common_pb2.WRITE_MODE_REPLACE)
    with client.open(PATH) as during:
        print(f"  G4, open() durante la escritura sin confirmar ve la versión anterior: {during.read(0, len(old) + 50) == old}")
print(f"  G3, quien abrió antes sigue leyendo su versión entera tras la confirmación: {reader.read(0, len(old) + 50) == old}")
reader.close()
with client.open(PATH) as after:
    print(f"  G2, un open() posterior ve la versión confirmada: {after.read(0, len(new) + 50) == new} (versión {after.version})")
client.close()
