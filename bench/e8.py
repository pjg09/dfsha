"""E8 por componentes (ADR 0046): lo que cuesta cada pieza de la seguridad, fuera de DFSha.

Se ejecuta con ``python -c <script> <modo> ...`` dentro de un contenedor de DFSha con los secretos del host:
- ``crypto <condición> <repeticiones>``: AES-256-GCM (cifrar y descifrar) y SHA-256 de bloques de 16 MiB, con
  las mismas funciones que usa el cliente. Escribe filas CSV.
- ``server <puerto> tls|plain``: servidor gRPC de prueba con dos métodos en flujo (enviar y recibir bytes).
- ``client <host:puerto> tls|plain <condición> <MiB> <repeticiones>``: transferencias contra ese servidor. Filas CSV.
Los mensajes son de 1 MiB, como en WriteBlock y ReadBlock (§5.2).
"""

import csv
import hashlib
import os
import sys
import time
from concurrent import futures
from pathlib import Path

import grpc

from dfsha.common.security import decrypt_block, encrypt_block, generate_key
from dfsha.common.tls import DEFAULT_SECRETS_DIRECTORY, get_server_credentials, load_identity, make_channel_factory

MIB = 1024 * 1024
UPLOAD = "/dfsha.bench.Transfer/Upload"
DOWNLOAD = "/dfsha.bench.Transfer/Download"
OPTIONS = [("grpc.max_receive_message_length", 4 * MIB), ("grpc.max_send_message_length", 4 * MIB)]
writer = csv.writer(sys.stdout)


def identity_bytes(value: bytes) -> bytes:
    return value


def crypto(condition: str, reps: int) -> None:
    key, block = generate_key(), os.urandom(16 * MIB)
    for rep in range(1, reps + 1):
        timings = {"aes-gcm-cifrar": 0.0, "aes-gcm-descifrar": 0.0, "sha256": 0.0}
        for index in range(16):  # 256 MiB por repetición
            block_id = f"bloque-{rep}-{index}"
            started = time.monotonic()
            stored = encrypt_block(key, block_id, block)
            timings["aes-gcm-cifrar"] += time.monotonic() - started
            started = time.monotonic()
            hashlib.sha256(stored).digest()
            timings["sha256"] += time.monotonic() - started
            started = time.monotonic()
            decrypt_block(key, block_id, stored)
            timings["aes-gcm-descifrar"] += time.monotonic() - started
        for operation, seconds in timings.items():
            writer.writerow([condition, rep, operation, 256, f"{seconds * 1000:.1f}", f"{256 * MIB / seconds / 1e6:.1f}", ""])


def serve(port: int, security: str) -> None:
    def upload(requests, _context):  # noqa: ANN001
        return str(sum(len(chunk) for chunk in requests)).encode()

    def download(request, _context):  # noqa: ANN001
        chunk = os.urandom(MIB)
        for _ in range(int(request)):
            yield chunk

    handler = grpc.method_handlers_generic_handler(
        "dfsha.bench.Transfer",
        {
            "Upload": grpc.stream_unary_rpc_method_handler(upload, identity_bytes, identity_bytes),
            "Download": grpc.unary_stream_rpc_method_handler(download, identity_bytes, identity_bytes),
        },
    )
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4), options=OPTIONS)
    server.add_generic_rpc_handlers((handler,))
    if security == "tls":
        server.add_secure_port(f"[::]:{port}", get_server_credentials(load_identity(Path(DEFAULT_SECRETS_DIRECTORY))))
    else:
        server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"servidor de prueba en {port} ({security})", file=sys.stderr, flush=True)
    server.wait_for_termination()


def client(addr: str, security: str, condition: str, size_mib: int, reps: int) -> None:
    if security == "tls":
        channel = make_channel_factory(load_identity(Path(DEFAULT_SECRETS_DIRECTORY)))(addr)
    else:
        channel = grpc.insecure_channel(addr, options=OPTIONS)
    upload = channel.stream_unary(UPLOAD, request_serializer=identity_bytes, response_deserializer=identity_bytes)
    download = channel.unary_stream(DOWNLOAD, request_serializer=identity_bytes, response_deserializer=identity_bytes)
    chunk = os.urandom(MIB)
    for rep in range(1, reps + 1):
        started = time.monotonic()
        received = int(upload(iter([chunk] * size_mib), timeout=120))
        up_s = time.monotonic() - started
        started = time.monotonic()
        downloaded = sum(len(part) for part in download(str(size_mib).encode(), timeout=120))
        down_s = time.monotonic() - started
        ok = received == downloaded == size_mib * MIB
        for operation, seconds in ((f"grpc-envio-{security}", up_s), (f"grpc-recepcion-{security}", down_s)):
            writer.writerow([condition, rep, operation, size_mib, f"{seconds * 1000:.1f}", f"{size_mib * MIB / seconds / 1e6:.1f}", ok])
        print(f"{security} rep {rep}: envío {size_mib * MIB / up_s / 1e6:.0f} MB/s, recepción {size_mib * MIB / down_s / 1e6:.0f} MB/s", file=sys.stderr, flush=True)
    channel.close()


mode, *arguments = sys.argv[1:]
if mode == "crypto":
    crypto(arguments[0], int(arguments[1]))
elif mode == "server":
    serve(int(arguments[0]), arguments[1])
else:
    client(arguments[0], arguments[1], arguments[2], int(arguments[3]), int(arguments[4]))
