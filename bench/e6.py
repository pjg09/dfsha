"""E6 (ADR 0046): lecturas durante la caída de un nodo de datos, vistas desde client-1.

``python -c <script> <segundos> <variante> <repetición>`` con DFSHA_* en el entorno: lee /bench/e6.bin una y
otra vez durante esos segundos y escribe una fila CSV por lectura: variante, repetición, hora UTC de inicio,
duración y resultado (ok, o el motivo o código del error).
"""

import csv
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from dfsha.client.client import DfshaClient, load_settings
from dfsha.common.errors import DfshaError

duration_s, variant, rep = float(sys.argv[1]), sys.argv[2], sys.argv[3]
client = DfshaClient(load_settings())
writer = csv.writer(sys.stdout)
target = Path("/data/e6-copia.bin")
deadline = time.monotonic() + duration_s
while time.monotonic() < deadline:
    started_at = datetime.now(UTC).strftime("%H:%M:%S.%f")[:-3]
    started = time.monotonic()
    try:
        client.get("/bench/e6.bin", target)
        result = "ok"
    except DfshaError as error:
        result = str(error.reason) if error.reason else error.code.name
    writer.writerow([variant, rep, started_at, f"{time.monotonic() - started:.2f}", result])
    sys.stdout.flush()
target.unlink(missing_ok=True)
client.close()
