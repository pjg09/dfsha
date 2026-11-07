"""Línea de órdenes de DFSha: dfsha <orden> o dfsha shell (fase I §2.3, ADR 0025).

El directorio actual vive en el cliente: ``cd`` solo existe en el modo interactivo y al servidor llegan
siempre rutas absolutas.
"""

import argparse
import getpass
import os
import posixpath
import shlex
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from dfsha.client.client import DfshaClient, load_settings
from dfsha.client.file_handle import FileHandle
from dfsha.common import config
from dfsha.common.config import ConfigError
from dfsha.common.errors import DfshaError
from dfsha.common.log import configure_logging
from dfsha.v1 import common_pb2, metadata_pb2


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
            "useradd": (1, 2, self.useradd),
            "read": (2, 4, self.read),
            "write": (2, 3, self.write),
            "append": (1, 2, self.append),
            "open": (1, 2, self.open),
            "lock": (0, 2, self.lock),
            "unlock": (0, 0, self.unlock),
            "close": (0, 0, self.close),
        }
        self.open_file: FileHandle | None = None  # solo en el modo interactivo

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


    # ----- RF3 (§7): con un archivo abierto en el shell, read, write y append actúan sobre él -----

    def read(self, *arguments: str) -> None:
        """read <ruta> <offset> <longitud> [destino]; con un archivo abierto, read <offset> <longitud> [destino]."""
        if self.open_file is None:
            if len(arguments) < 3:
                raise ValueError("read <ruta> <offset> <longitud> [destino]")
            path, offset, length, *target = arguments
            with self.client.open(self._remote(path)) as handle:
                data = handle.read(_parse_int(offset), _parse_int(length))
        else:
            if not 2 <= len(arguments) <= 3:
                raise ValueError("Con un archivo abierto: read <offset> <longitud> [destino]")
            offset, length, *target = arguments
            data = self.open_file.read(_parse_int(offset), _parse_int(length))
        if target:
            Path(target[0]).write_bytes(data)
            print(f"{target[0]}: {_format_size(len(data))}")
        else:
            sys.stdout.buffer.write(data)
            sys.stdout.flush()

    def write(self, *arguments: str) -> None:
        """write <ruta> <offset> <datos> (modificación parcial); con un archivo abierto, write <offset> <datos> [modo]."""
        if self.open_file is None:
            if len(arguments) != 3:
                raise ValueError("write <ruta> <offset> <datos>")
            path, offset, source = arguments
            self._write_and_close(path, _parse_int(offset), _read_data(source), common_pb2.WRITE_MODE_PARTIAL)
        else:
            offset, source, *mode = arguments
            self.open_file.write(_read_data(source), _parse_int(offset), _parse_write_mode(mode[0]) if mode else None)

    def append(self, *arguments: str) -> None:
        """append <ruta> <datos>; con un archivo abierto, append <datos>."""
        if self.open_file is None:
            if len(arguments) != 2:
                raise ValueError("append <ruta> <datos>")
            self._write_and_close(arguments[0], 0, _read_data(arguments[1]), common_pb2.WRITE_MODE_APPEND)
        else:
            if len(arguments) != 1:
                raise ValueError("Con un archivo abierto: append <datos>")
            self.open_file.write(_read_data(arguments[0]), mode=common_pb2.WRITE_MODE_APPEND)

    def open(self, path: str, mode: str = "r") -> None:
        if self.open_file is not None:
            raise ValueError(f"Ya está abierto {self.open_file.path}; ciérralo con close")
        if mode not in _OPEN_MODES:
            raise ValueError("open <ruta> [r|w|c]: r para leer, w para escribir uno que existe, c para crearlo")
        self.open_file = self.client.open(self._remote(path), _OPEN_MODES[mode])
        print(f"{self.open_file.path}: abierto, versión {self.open_file.version}, {_format_size(self.open_file.size)}")

    def lock(self, first_block: str = "0", block_count: str = "0") -> None:
        """lock [primer-bloque] [número-de-bloques]; 0 bloques llega hasta el final del archivo."""
        self._require_open_file().lock(_parse_int(first_block), _parse_int(block_count))

    def unlock(self) -> None:
        self._require_open_file().unlock()

    def close(self) -> None:
        handle = self._require_open_file()
        self.open_file = None
        print(f"{handle.path}: versión {handle.close()}")

    def discard_open_file(self) -> None:
        """Al salir del shell, las escrituras que no se cerraron se descartan."""
        if self.open_file is not None:
            print(f"{self.open_file.path} seguía abierto: se descartan sus escrituras sin confirmar", file=sys.stderr)
            self.open_file.abort()
            self.open_file = None

    def _require_open_file(self) -> FileHandle:
        if self.open_file is None:
            raise ValueError("No hay ningún archivo abierto; usa open <ruta> [r|w|c]")
        return self.open_file

    def _write_and_close(self, path: str, offset: int, data: bytes, mode: common_pb2.WriteMode) -> None:
        with self.client.open(self._remote(path), metadata_pb2.OPEN_MODE_WRITE) as handle:
            handle.write(data, offset, mode)
        print(f"{handle.path}: versión {handle.version}, {_format_size(handle.size)}")

    def useradd(self, username: str, role: str = "") -> None:
        if role not in ("", "admin"):
            raise ValueError("useradd <nombre> [admin]")
        password = os.environ.get("DFSHA_NEW_PASSWORD") or _ask_new_password(username)
        user_id = self.client.create_user(username, password, is_admin=role == "admin")
        print(f"Usuario {username} creado ({user_id}){' como administrador' if role else ''}")


_OPEN_MODES = {"r": metadata_pb2.OPEN_MODE_READ, "w": metadata_pb2.OPEN_MODE_WRITE, "c": metadata_pb2.OPEN_MODE_CREATE}
_WRITE_MODES = {
    "crear": common_pb2.WRITE_MODE_CREATE,
    "reemplazar": common_pb2.WRITE_MODE_REPLACE,
    "anexar": common_pb2.WRITE_MODE_APPEND,
    "parcial": common_pb2.WRITE_MODE_PARTIAL,
}


def _parse_int(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        raise ValueError(f"Se esperaba un número: {text!r}") from None


def _parse_write_mode(text: str) -> common_pb2.WriteMode:
    if text not in _WRITE_MODES:
        raise ValueError(f"Modo de escritura no válido: {text}. Modos: {', '.join(_WRITE_MODES)}")
    return _WRITE_MODES[text]


def _read_data(source: str) -> bytes:
    """Los datos de write y append: ``=texto`` es el texto literal; si no, un archivo local."""
    return source[1:].encode() if source.startswith("=") else Path(source).read_bytes()


def _ask_new_password(username: str) -> str:
    first = getpass.getpass(f"Contraseña para {username}: ")
    if first != getpass.getpass("Repítela: "):
        raise ValueError("Las contraseñas no coinciden")
    return first


def _report(error: Exception) -> None:
    if isinstance(error, DfshaError):
        reason = f" [{error.reason}]" if error.reason else f" [{error.code.name}]"
        print(f"Error: {error.message}{reason}", file=sys.stderr)
    else:
        print(f"Error: {error}", file=sys.stderr)


def _interactive(shell: Shell) -> None:
    print("DFSha. Órdenes: ls, cd, pwd, mkdir, rmdir, rm, mv, put, get, stat, read, write, append, open, lock, unlock, close, useradd, exit")
    try:
        _read_commands(shell)
    finally:
        shell.discard_open_file()


def _read_commands(shell: Shell) -> None:
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
    parser = argparse.ArgumentParser(
        prog="dfsha",
        description="Cliente de DFSha. Se configura con DFSHA_METADATA_ADDRS, DFSHA_USERNAME y DFSHA_PASSWORD "
        "(si falta, la pide) y DFSHA_SECRETS_DIRECTORY con el certificado del host.",
    )
    parser.add_argument("words", nargs="+", metavar="orden", help="ls, mkdir, rmdir, rm, mv, put, get, stat, read, write, append, useradd o shell")
    parser.add_argument("-v", "--verbose", action="store_true", help="muestra los reintentos y los avisos")
    arguments = parser.parse_args(argv)
    configure_logging("INFO" if arguments.verbose else "ERROR", "client")
    try:
        password = None if os.environ.get("DFSHA_PASSWORD") else getpass.getpass(f"Contraseña de {config.get_str('USERNAME')}: ")
        client = DfshaClient(load_settings(password))
    except (ConfigError, ValueError, OSError) as error:
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
