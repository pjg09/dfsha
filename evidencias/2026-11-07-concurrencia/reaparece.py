"""Variante de §11.1: P1 deja de renovar su arrendamiento y reaparece pasado el TTL de 30 s.

Se ejecuta en client-1 con DFSHA_* en el entorno: python -c <script>.
"""

import time

from dfsha.client.client import DfshaClient, load_settings
from dfsha.common.errors import DfshaError

client = DfshaClient(load_settings())
p1 = client.open("/datos.bin", 2)  # OPEN_MODE_WRITE
p1.write(b"P1-reaparece", 3 * p1.block_size)
assert p1._keeper is not None
p1._keeper.stop()  # deja de renovar, como un proceso parado
started = time.monotonic()
print(f"P1 tiene el arrendamiento y deja de renovarlo; espera 35 s (TTL de 30 s)", flush=True)
time.sleep(35)
try:
    version = p1.close()
    print(f"P1 confirma tras {time.monotonic() - started:.0f} s: versión {version} (NO DEBERÍA)")
except DfshaError as error:
    print(f"P1 confirma tras {time.monotonic() - started:.0f} s: rechazado, {error.code.name} [{error.reason}]: {error.message}")
client.close()
