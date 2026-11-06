"""DFSha: sistema de archivos distribuido con alta disponibilidad."""

from importlib.metadata import PackageNotFoundError, version

try:
    # La versión sale de la etiqueta vX.Y.Z de Git al instalar el paquete (ADR 0038)
    __version__ = version("dfsha")
except PackageNotFoundError:  # ejecutado sin instalar
    __version__ = "0.0.0"
