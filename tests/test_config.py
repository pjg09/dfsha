"""Lectura de la configuración desde variables DFSHA_*."""

import pytest

from dfsha.common.config import (
    ConfigError,
    get_addr,
    get_addrs,
    get_float,
    get_int,
    get_str,
    parse_addr,
)


def test_reads_with_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DFSHA_REPLICATION_FACTOR", "3")
    monkeypatch.setenv("DFSHA_LOG_LEVEL", " DEBUG ")
    assert get_int("REPLICATION_FACTOR") == 3
    assert get_str("LOG_LEVEL") == "DEBUG"


def test_default_when_missing_or_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DFSHA_HEARTBEAT_INTERVAL_S", raising=False)
    assert get_float("HEARTBEAT_INTERVAL_S", 3.0) == 3.0
    monkeypatch.setenv("DFSHA_HEARTBEAT_INTERVAL_S", "")
    assert get_float("HEARTBEAT_INTERVAL_S", 3.0) == 3.0


def test_missing_without_default_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DFSHA_METADATA_ADDRS", raising=False)
    with pytest.raises(ConfigError, match="DFSHA_METADATA_ADDRS"):
        get_addrs("METADATA_ADDRS")


def test_invalid_number_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DFSHA_REPLICATION_FACTOR", "tres")
    with pytest.raises(ConfigError, match="entero"):
        get_int("REPLICATION_FACTOR")


def test_addr_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DFSHA_METADATA_ADDRS", "metadata-1:50051, metadata-2:50051,metadata-3:50051")
    assert get_addrs("METADATA_ADDRS") == [
        "metadata-1:50051",
        "metadata-2:50051",
        "metadata-3:50051",
    ]


def test_addr_needs_matching_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DFSHA_DATANODE_ADDR", "datanode-1:50052")
    assert get_addr("DATANODE_ADDR") == "datanode-1:50052"
    with pytest.raises(ConfigError, match="_ADDRS"):
        get_addrs("DATANODE_ADDR")


@pytest.mark.parametrize("addr", ["datanode-1", ":50052", "datanode-1:puerto", "datanode-1:70000"])
def test_parse_addr_rejects_invalid(addr: str) -> None:
    with pytest.raises(ConfigError):
        parse_addr(addr)


def test_parse_addr() -> None:
    assert parse_addr("metadata-2:50051") == ("metadata-2", 50051)
