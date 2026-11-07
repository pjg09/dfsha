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


def blocks(client: DfshaClient, writer: "csv._writer", condition: str, count: int, reps: int) -> None:
    """E3: latencia de escribir un bloque (WriteBlock hasta W réplicas). Se reserva, se escribe y se aborta."""
    from dfsha.client.client import WHOLE_FILE, _request_id
    from dfsha.common.security import encrypt_block
    from dfsha.v1 import metadata_pb2

    for rep in range(1, reps + 1):
        path = f"/bench/{condition}-bloques.bin"
        opened = client.metadata.call_rpc("OpenFile", metadata_pb2.OpenFileRequest(path=path, mode=metadata_pb2.OPEN_MODE_CREATE))
        lease = client.metadata.call_rpc(
            "LockBlocks", metadata_pb2.LockBlocksRequest(request_id=_request_id(), file_handle=opened.file_handle, block_range=WHOLE_FILE)
        )
        size = opened.info.block_size_bytes
        latencies = []
        for location in client._allocate(opened.file_handle, lease.lease_id, list(range(count))):
            stored = encrypt_block(opened.data_key, location.block_id, os.urandom(size))
            sha256 = hashlib.sha256(stored).digest()
            started = time.monotonic()
            client._write_block(location, stored, sha256)  # solo la escritura: sin cifrado ni hash en el tiempo
            seconds = time.monotonic() - started
            latencies.append(seconds)
            writer.writerow([condition, rep, "bloque", size // MIB, f"{seconds * 1000:.1f}", f"{size / seconds / 1e6:.1f}", ""])
        client._abort(opened.file_handle, lease.lease_id)
        client._unlock(lease.lease_id)
        log(f"{condition} rep {rep}: {count} bloques, mediana {sorted(latencies)[len(latencies) // 2] * 1000:.0f} ms")


def partial(client: DfshaClient, writer: "csv._writer", condition: str, size_mib: int, reps: int) -> None:
    """E5: latencia de una modificación parcial de 4 KiB en medio de un archivo (reescribe un bloque entero)."""
    from dfsha.v1 import common_pb2, metadata_pb2

    local = make_file(size_mib)
    remote = f"/bench/{condition}-parcial.bin"
    try:
        client.delete_file(remote)
    except DfshaError:
        pass
    client.put(Path(local), remote)
    os.remove(local)
    for rep in range(1, reps + 1):
        offset = size_mib * MIB // 2 + rep * 4096
        started = time.monotonic()
        with client.open(remote, metadata_pb2.OPEN_MODE_WRITE) as handle:
            handle.write(os.urandom(4096), offset, common_pb2.WRITE_MODE_PARTIAL)
        seconds = time.monotonic() - started
        writer.writerow([condition, rep, "parcial-4kib", size_mib, f"{seconds * 1000:.1f}", f"{4096 / seconds / 1e6:.3f}", ""])
        log(f"{condition} modificación parcial rep {rep}: {seconds * 1000:.0f} ms")
    client.delete_file(remote)


def concurrent(writer: "csv._writer", condition: str, clients: int, mode: str, size_mib: int, reps: int) -> None:
    """E4: N clientes a la vez, cada uno con su conexión y su token.

    distinct: cada cliente carga y recupera su propio archivo; tasa agregada = bytes totales / tiempo del más lento.
    same: todos modifican el mismo bloque del mismo archivo; se cuentan los conflictos hasta confirmar.
    """
    import threading
    from dataclasses import replace

    from dfsha.common.errors import Reason
    from dfsha.v1 import common_pb2, metadata_pb2

    settings = replace(load_settings(), parallel_transfers=1)  # la concurrencia la ponen los clientes
    pool = [DfshaClient(settings) for _ in range(clients)]
    local = make_file(size_mib)
    for rep in range(1, reps + 1):
        barrier = threading.Barrier(clients)
        results: list[tuple[str, float, int]] = []

        def work(index: int) -> None:
            client = pool[index]
            if mode == "distinct":
                remote = f"/bench/{condition}-{index}.bin"
                try:
                    client.delete_file(remote)
                except DfshaError:
                    pass
                barrier.wait()
                started = time.monotonic()
                client.put(Path(local), remote)
                results.append(("put", time.monotonic() - started, 0))
                barrier.wait()
                copy = f"{DATA}/bench-copia-{index}.bin"
                started = time.monotonic()
                client.get(remote, Path(copy))
                results.append(("get", time.monotonic() - started, 0))
                os.remove(copy)
                client.delete_file(remote)
                return
            barrier.wait()
            started, conflicts = time.monotonic(), 0
            while True:
                try:
                    with client.open(f"/bench/{condition}-mismo.bin", metadata_pb2.OPEN_MODE_WRITE) as handle:
                        handle.write(os.urandom(4096), index * 4096, common_pb2.WRITE_MODE_PARTIAL)
                    break
                except DfshaError as error:
                    if error.reason not in (Reason.LOCK_CONFLICT, Reason.VERSION_CONFLICT):
                        raise
                    conflicts += 1
                    time.sleep(0.05 * (1 + conflicts % 4))
            results.append(("escritura-mismo-bloque", time.monotonic() - started, conflicts))

        if mode == "same":
            pool[0].put(Path(local), f"/bench/{condition}-mismo.bin")
        threads = [threading.Thread(target=work, args=(index,)) for index in range(clients)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        for operation in sorted({result[0] for result in results}):
            times = [seconds for name, seconds, _ in results if name == operation]
            conflicts = sum(count for name, _, count in results if name == operation)
            for name, seconds, count in results:
                if name == operation:
                    writer.writerow([condition, rep, operation, size_mib, f"{seconds * 1000:.1f}", f"{size_mib * MIB / seconds / 1e6:.1f}", count])
            aggregate = len(times) * size_mib * MIB / max(times) / 1e6
            writer.writerow([condition, rep, f"{operation}-agregada", size_mib, f"{max(times) * 1000:.1f}", f"{aggregate:.1f}", conflicts])
            log(f"{condition} rep {rep} {operation}: más lento {max(times):.2f} s, agregada {aggregate:.0f} MB/s, conflictos {conflicts}")
        if mode == "same":
            pool[0].delete_file(f"/bench/{condition}-mismo.bin")
    os.remove(local)
    for client in pool:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["transfer", "blocks", "partial", "concurrent"])
    parser.add_argument("--condition", required=True)
    parser.add_argument("--sizes", default="16,256,1024")
    parser.add_argument("--reps", type=int, default=5)
    parser.add_argument("--count", type=int, default=16, help="blocks: bloques por repetición")
    parser.add_argument("--clients", type=int, default=1, help="concurrent: clientes a la vez")
    parser.add_argument("--mode", choices=["distinct", "same"], default="distinct", help="concurrent")
    arguments = parser.parse_args(sys.argv[1:])
    client = DfshaClient(load_settings())
    try:
        client.create_directory("/bench")
    except DfshaError:
        pass
    writer = csv.writer(sys.stdout)
    sizes = [int(size) for size in arguments.sizes.split(",")]
    if arguments.command == "transfer":
        transfer(client, writer, arguments.condition, sizes, arguments.reps)
    elif arguments.command == "blocks":
        blocks(client, writer, arguments.condition, arguments.count, arguments.reps)
    elif arguments.command == "partial":
        partial(client, writer, arguments.condition, sizes[0], arguments.reps)
    else:
        concurrent(writer, arguments.condition, arguments.clients, arguments.mode, sizes[0], arguments.reps)
    client.close()


main()
