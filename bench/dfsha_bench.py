"""Mediciones de los experimentos de la fase I §12 (ADR 0028), dentro de client-1 con la biblioteca del cliente.

Se ejecuta como ``python -c <script> <orden> [opciones]`` con DFSHA_* en el entorno y escribe en la salida
estándar una fila CSV por medición (sin cabecera: la pone bench/ejecutar.sh). El progreso va a la salida de
error. Los tiempos se miden en el cliente (§12.3); MB son 10^6 bytes y MiB 2^20 (C21).
"""

import argparse
import csv
import hashlib
import os
import sys
import time
from pathlib import Path

from dfsha.client.client import DfshaClient, load_settings
from dfsha.common.errors import DfshaError

MIB = 1024 * 1024
DATA = "/data"


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        while chunk := source.read(4 * MIB):
            digest.update(chunk)
    return digest.hexdigest()


def make_file(size_mib: int) -> str:
    path = f"{DATA}/bench-{size_mib}mib.bin"
    if not os.path.exists(path) or os.path.getsize(path) != size_mib * MIB:
        with open(path, "wb") as target:
            for _ in range(size_mib):
                target.write(os.urandom(MIB))  # contenido aleatorio: ninguna capa comprime (§12.3)
    return path


def transfer(client: DfshaClient, writer: "csv._writer", condition: str, sizes: list[int], reps: int) -> None:
    """E1, E2, E3, E5 y E8: put y get de archivos completos; cada put es una creación."""
    for size_mib in sizes:
        local = make_file(size_mib)
        expected = sha256_of(local)
        remote = f"/bench/{condition}-{size_mib}mib.bin"
        for rep in range(1, reps + 1):
            try:
                client.delete_file(remote)
            except DfshaError:
                pass
            started = time.monotonic()
            client.put(Path(local), remote)
            put_s = time.monotonic() - started
            copy = f"{DATA}/bench-copia.bin"
            started = time.monotonic()
            client.get(remote, Path(copy))
            get_s = time.monotonic() - started
            ok = sha256_of(copy) == expected
            os.remove(copy)
            for operation, seconds in (("put", put_s), ("get", get_s)):
                writer.writerow([condition, rep, operation, size_mib, f"{seconds * 1000:.1f}", f"{size_mib * MIB / seconds / 1e6:.1f}", ok])
            log(f"{condition} {size_mib} MiB rep {rep}: put {put_s:.2f} s, get {get_s:.2f} s, hash {'ok' if ok else 'DISTINTO'}")
        client.delete_file(remote)
        os.remove(local)  # el disco de client-1 es pequeño (6,7 GiB)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["transfer"])
    parser.add_argument("--condition", required=True)
    parser.add_argument("--sizes", default="16,256,1024")
    parser.add_argument("--reps", type=int, default=5)
    arguments = parser.parse_args(sys.argv[1:])
    client = DfshaClient(load_settings())
    try:
        client.create_directory("/bench")
    except DfshaError:
        pass
    writer = csv.writer(sys.stdout)
    transfer(client, writer, arguments.condition, [int(size) for size in arguments.sizes.split(",")], arguments.reps)
    client.close()


main()
