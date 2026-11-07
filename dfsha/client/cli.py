"""Línea de órdenes de DFSha: dfsha <orden> o dfsha shell (fase I §2.3, ADR 0025).

El directorio actual vive en el cliente: ``cd`` solo existe en el modo interactivo y al servidor llegan
siempre rutas absolutas.
"""

import argparse
import posixpath
import shlex
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from dfsha.client.client import DfshaClient, load_settings
from dfsha.common.config import ConfigError
from dfsha.common.errors import DfshaError
from dfsha.common.log import configure_logging
from dfsha.v1 import metadata_pb2


def resolve_path(current_directory: str, path: str) -> str:
    """Convierte una ruta relativa al directorio actual en absoluta, resolviendo . y .."""
    joined = path if path.startswith("/") else posixpath.join(current_directory, path)
    normalized = posixpath.normpath(joined)
    return "/" if normalized in ("/", "//") else normalized


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    value = float(size_bytes)
    for unit in ("KiB", "MiB", "GiB", "TiB"):
        value /= 1024
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}"
    raise AssertionError("inalcanzable")


def _format_time(entry: metadata_pb2.DirectoryEntry | metadata_pb2.FileInfo) -> str:
    seconds = entry.modified_at.ToNanoseconds() / 1e9
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%d %H:%M") if seconds else "-"


class Shell:
    def __init__(self, client: DfshaClient) -> None:
        self.client = client
        self.current_directory = "/"
        self._commands: dict[str, tuple[int, int, Callable[..., None]]] = {
            "ls": (0, 1, self.ls),
            "cd": (0, 1, self.cd),
            "pwd": (0, 0, self.pwd),
            "mkdir": (1, 1, self.mkdir),
            "rmdir": (1, 1, self.rmdir),
            "rm": (1, 1, self.rm),
            "mv": (2, 2, self.mv),
            "put": (2, 2, self.put),
            "get": (2, 2, self.get),
            "stat": (1, 1, self.stat),
        }

    def run(self, words: list[str]) -> None:
        command, *arguments = words
        spec = self._commands.get(command)
        if spec is None:
            raise ValueError(f"Orden desconocida: {command}. Órdenes: {', '.join(self._commands)}")
        minimum, maximum, handler = spec
        if not minimum <= len(arguments) <= maximum:
            raise ValueError(f"{command} espera entre {minimum} y {maximum} argumentos")
        handler(*arguments)

    def _remote(self, path: str) -> str:
        return resolve_path(self.current_directory, path)

    def ls(self, path: str = ".") -> None:
        for entry in self.client.list_directory(self._remote(path)):
            if entry.type == metadata_pb2.ENTRY_TYPE_DIRECTORY:
                print(f"d  {'-':>10}  {'':>4}  {_format_time(entry)}  {entry.name}/")
            else:
                print(f"-  {_format_size(entry.size_bytes):>10}  v{entry.version:<3}  {_format_time(entry)}  {entry.name}")

    def cd(self, path: str = "/") -> None:
        target = self._remote(path)
        if target != "/":
            entries = self.client.list_directory(posixpath.dirname(target))
            name = posixpath.basename(target)
            if not any(entry.name == name and entry.type == metadata_pb2.ENTRY_TYPE_DIRECTORY for entry in entries):
                raise ValueError(f"No es un directorio: {target}")
        self.current_directory = target

    def pwd(self) -> None:
        print(self.current_directory)

    def mkdir(self, path: str) -> None:
        self.client.create_directory(self._remote(path))

    def rmdir(self, path: str) -> None:
        self.client.delete_directory(self._remote(path))

    def rm(self, path: str) -> None:
        self.client.delete_file(self._remote(path))

    def mv(self, source: str, target: str) -> None:
        self.client.move(self._remote(source), self._remote(target))

    def put(self, local: str, remote: str) -> None:
        local_path = Path(local)
        started = time.monotonic()
        version = self.client.put(local_path, self._remote(remote))
        elapsed = time.monotonic() - started
        size = local_path.stat().st_size
        print(f"{self._remote(remote)}: versión {version}, {_format_size(size)} en {elapsed:.1f} s ({size / 1e6 / max(elapsed, 1e-9):.0f} MB/s)")

    def get(self, remote: str, local: str) -> None:
        started = time.monotonic()
        size = self.client.get(self._remote(remote), Path(local))
        elapsed = time.monotonic() - started
        print(f"{local}: {_format_size(size)} en {elapsed:.1f} s ({size / 1e6 / max(elapsed, 1e-9):.0f} MB/s)")

    def stat(self, path: str) -> None:
        info = self.client.get_file_info(self._remote(path))
        print(f"ruta: {info.path}\nversión: {info.version}\ntamaño: {info.size_bytes} bytes ({_format_size(info.size_bytes)})")
        print(f"bloques: {info.block_count} de {_format_size(info.block_size_bytes)}\nmodificado: {_format_time(info)}")


def _report(error: Exception) -> None:
    if isinstance(error, DfshaError):
        reason = f" [{error.reason}]" if error.reason else f" [{error.code.name}]"
        print(f"Error: {error.message}{reason}", file=sys.stderr)
    else:
        print(f"Error: {error}", file=sys.stderr)


def _interactive(shell: Shell) -> None:
    print("DFSha. Órdenes: ls, cd, pwd, mkdir, rmdir, rm, mv, put, get, stat, exit")
    while True:
        try:
            line = input(f"dfsha:{shell.current_directory}> ")
        except EOFError:
            print()
            return
        words = shlex.split(line)
        if not words:
            continue
        if words[0] in ("exit", "quit"):
            return
        try:
            shell.run(words)
        except (DfshaError, ValueError, OSError) as error:
            _report(error)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dfsha", description="Cliente de DFSha. Se configura con DFSHA_METADATA_ADDRS.")
    parser.add_argument("words", nargs="+", metavar="orden", help="ls, mkdir, rmdir, rm, mv, put, get, stat o shell")
    parser.add_argument("-v", "--verbose", action="store_true", help="muestra los reintentos y los avisos")
    arguments = parser.parse_args(argv)
    configure_logging("INFO" if arguments.verbose else "ERROR", "client")
    try:
        client = DfshaClient(load_settings())
    except (ConfigError, ValueError) as error:
        _report(error)
        return 2
    with client:
        shell = Shell(client)
        if arguments.words == ["shell"]:
            _interactive(shell)
            return 0
        try:
            shell.run(arguments.words)
        except (DfshaError, ValueError, OSError) as error:
            _report(error)
            return 1
    return 0
