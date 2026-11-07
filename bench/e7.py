"""E7 (ADR 0046): servicio de metadatos durante la caída del líder, visto desde client-1.

Modos (se ejecuta con ``python -c <script> <modo> ...`` y DFSHA_* en el entorno):
- ``leader``: escribe la dirección del líder actual.
- ``probe <segundos> <repetición>``: un mkdir cada 0,1 s, con 1 s de plazo y sin reintentos, durante esos
  segundos. Si un servidor no responde, pasa al siguiente, como el cliente. Escribe una fila CSV por intento:
  repetición, hora UTC, latencia y resultado (ok, SAFE_MODE_ACTIVE, NODE_NOT_LEADER o el código de error).
"""

import csv
import sys
import time
import uuid
from dataclasses import replace
from datetime import UTC, datetime

from dfsha.client.client import DfshaClient, load_settings
from dfsha.client.connection import RetryPolicy
from dfsha.common.errors import DfshaError, Reason
from dfsha.v1 import metadata_pb2

settings = replace(load_settings(), rpc_timeout_s=1.0, retry=RetryPolicy(max_attempts=1, max_total_s=1.0))
client = DfshaClient(settings)
mode, *arguments = sys.argv[1:]

if mode == "leader":
    client.list_directory("/")  # sigue la redirección hasta el líder
    print(client.metadata._leader_addr)
    sys.exit(0)

duration_s, rep = float(arguments[0]), arguments[1]
writer = csv.writer(sys.stdout)
try:
    client.create_directory("/bench")
except DfshaError:
    pass
deadline = time.monotonic() + duration_s
while time.monotonic() < deadline:
    addr = client.metadata._leader_addr
    request = metadata_pb2.CreateDirectoryRequest(request_id=str(uuid.uuid4()), path=f"/bench/e7-{uuid.uuid4().hex[:12]}")
    started = time.monotonic()
    try:
        client.metadata.call_rpc("CreateDirectory", request)
        result = "ok"
    except DfshaError as error:
        result = str(error.reason) if error.reason else error.code.name
        if error.reason is not Reason.SAFE_MODE_ACTIVE:
            client.metadata._switch_server(addr)  # no responde o no es el líder: prueba otro
    latency_ms = (time.monotonic() - started) * 1000
    writer.writerow([rep, datetime.now(UTC).strftime("%H:%M:%S.%f")[:-3], f"{latency_ms:.1f}", result, addr])
    sys.stdout.flush()
    time.sleep(max(0.0, 0.1 - latency_ms / 1000))
client.close()
