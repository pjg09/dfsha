"""Formato común de los logs."""

import logging
import re

import pytest

from dfsha.common.log import configure_logging


def test_log_line_has_utc_time_and_node_name(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", node_name="datanode-2")
    logging.getLogger("dfsha.datanode").info("Bloque 3 replicado en datanode-4")
    line = capsys.readouterr().out.strip()
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z INFO datanode-2 dfsha\.datanode: "
        r"Bloque 3 replicado en datanode-4",
        line,
    ), line


def test_level_filters_debug(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("info", node_name="metadata-1")
    logging.getLogger("dfsha").debug("no debe salir")
    assert capsys.readouterr().out == ""
