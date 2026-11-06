"""Configuración de los logs, igual en todos los roles.

Cada línea lleva la hora en UTC con milisegundos y el nombre de host del nodo
(convenciones §4: el mismo nombre en logs, diagramas y documentación), para poder
ordenar juntos los logs de varios nodos.
"""

import logging
import socket
import sys
import time

LOG_FORMAT = "%(asctime)s.%(msecs)03dZ %(levelname)s %(node_name)s %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


class _NodeNameFilter(logging.Filter):
    def __init__(self, node_name: str) -> None:
        super().__init__()
        self._node_name = node_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.node_name = self._node_name
        return True


def configure_logging(level: str = "INFO", node_name: str | None = None) -> None:
    """Envía los logs a la salida estándar con el formato común del clúster."""
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    formatter.converter = time.gmtime
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(_NodeNameFilter(node_name or socket.gethostname()))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
