"""Validación de rutas del espacio de nombres de un usuario (ADR 0025)."""

import grpc

from dfsha.common.errors import DfshaError, Reason

MAX_NAME_BYTES = 255
MAX_DEPTH = 64


def split_path(path: str) -> list[str]:
    """Separa una ruta absoluta en sus componentes; ``/`` es la lista vacía.

    Rechaza rutas relativas, componentes vacíos, ``.`` y ``..``, nombres de más de 255 bytes y
    caracteres de control. El cliente resuelve ``cd`` y las rutas relativas antes de llamar (§2.3).
    """
    if not path.startswith("/"):
        raise _invalid(path, "tiene que ser absoluta")
    if path == "/":
        return []
    components = path.removesuffix("/").split("/")[1:]
    if len(components) > MAX_DEPTH:
        raise _invalid(path, f"tiene más de {MAX_DEPTH} niveles")
    for name in components:
        if name in ("", ".", ".."):
            raise _invalid(path, "tiene un componente vacío, . o ..")
        if len(name.encode()) > MAX_NAME_BYTES:
            raise _invalid(path, f"tiene un nombre de más de {MAX_NAME_BYTES} bytes")
        if any(ord(char) < 32 or char == "\x7f" for char in name):
            raise _invalid(path, "tiene caracteres de control")
    return components


def _invalid(path: str, problem: str) -> DfshaError:
    return DfshaError(grpc.StatusCode.INVALID_ARGUMENT, f"La ruta {path!r} {problem}", Reason.PATH_INVALID)
