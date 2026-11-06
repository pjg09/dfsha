"""Lectura de la configuración desde variables de entorno.

Todas las variables llevan el prefijo DFSHA_ (convenciones §2): el código pide
``METADATA_ADDRS`` y se lee ``DFSHA_METADATA_ADDRS``. Las direcciones son siempre
``host:puerto`` y se resuelven por nombre (RNF7).
"""

import os

VARIABLE_PREFIX = "DFSHA_"


class ConfigError(ValueError):
    """Una variable de configuración falta o tiene un valor no válido."""


def _get_raw(name: str) -> str | None:
    value = os.environ.get(VARIABLE_PREFIX + name)
    if value is None or value.strip() == "":
        return None
    return value.strip()


def get_str(name: str, default: str | None = None) -> str:
    """Devuelve el texto de DFSHA_<name>, o el valor por defecto si no está definida."""
    value = _get_raw(name)
    if value is not None:
        return value
    if default is not None:
        return default
    raise ConfigError(f"Falta la variable de entorno {VARIABLE_PREFIX}{name}")


def get_int(name: str, default: int | None = None) -> int:
    """Devuelve DFSHA_<name> como entero."""
    value = _get_raw(name)
    if value is None:
        if default is not None:
            return default
        raise ConfigError(f"Falta la variable de entorno {VARIABLE_PREFIX}{name}")
    try:
        return int(value)
    except ValueError:
        raise ConfigError(f"{VARIABLE_PREFIX}{name} debe ser un entero: {value!r}") from None


def get_float(name: str, default: float | None = None) -> float:
    """Devuelve DFSHA_<name> como número decimal."""
    value = _get_raw(name)
    if value is None:
        if default is not None:
            return default
        raise ConfigError(f"Falta la variable de entorno {VARIABLE_PREFIX}{name}")
    try:
        return float(value)
    except ValueError:
        raise ConfigError(f"{VARIABLE_PREFIX}{name} debe ser un número: {value!r}") from None


def parse_addr(addr: str) -> tuple[str, int]:
    """Separa una dirección ``host:puerto`` en sus dos partes y la valida."""
    host, separator, port_text = addr.strip().rpartition(":")
    if not separator or not host:
        raise ConfigError(f"La dirección debe tener la forma host:puerto: {addr!r}")
    try:
        port = int(port_text)
    except ValueError:
        raise ConfigError(f"El puerto de {addr!r} no es un número") from None
    if not 1 <= port <= 65535:
        raise ConfigError(f"El puerto de {addr!r} está fuera de rango")
    return host, port


def get_addr(name: str, default: str | None = None) -> str:
    """Devuelve DFSHA_<name> como una dirección ``host:puerto`` validada."""
    if not name.endswith("_ADDR"):
        raise ConfigError(f"Una variable de dirección termina en _ADDR: {name}")
    addr = get_str(name, default)
    parse_addr(addr)
    return addr


def get_addrs(name: str, default: str | None = None) -> list[str]:
    """Devuelve DFSHA_<name> como lista de direcciones separadas por comas (ADR 0021)."""
    if not name.endswith("_ADDRS"):
        raise ConfigError(f"Una variable de lista de direcciones termina en _ADDRS: {name}")
    addrs = [item.strip() for item in get_str(name, default).split(",") if item.strip()]
    if not addrs:
        raise ConfigError(f"{VARIABLE_PREFIX}{name} no contiene ninguna dirección")
    for addr in addrs:
        parse_addr(addr)
    return addrs
