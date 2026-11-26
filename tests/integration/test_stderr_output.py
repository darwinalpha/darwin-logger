"""Integration tests for stderr and JSON output."""

from __future__ import annotations

import json
import logging

from darwin_logger import (
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
    set_log_level,
)


def test_text_output_goes_to_stderr(capsys) -> None:
    configure_logging(level="INFO", fmt="%(levelname)s %(message)s", use_color=False, from_env=False)
    get_logger("cli").info("started")
    captured = capsys.readouterr()
    assert captured.err == "INFO started\n"
    assert captured.out == ""


def test_debug_hidden_and_then_enabled(capsys) -> None:
    configure_logging(level="INFO", fmt="%(message)s", use_color=False, from_env=False)
    logger = get_logger("cli")
    logger.debug("hidden")
    set_log_level("DEBUG")
    logger.debug("visible")
    captured = capsys.readouterr()
    assert "hidden" not in captured.err
    assert "visible" in captured.err


def test_json_output_is_ingestible(capsys) -> None:
    configure_logging(
        level="INFO", json=True, service="fetch", env="test", use_color=False, from_env=False
    )
    token = bind_context(run_id="run-42", source="tushare")
    try:
        get_logger("worker").info("fetched", extra={"rows": 120})
    finally:
        clear_context(token)
    line = capsys.readouterr().err.strip()
    payload = json.loads(line)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "worker"
    assert payload["message"] == "fetched"
    assert payload["service"] == "fetch"
    assert payload["env"] == "test"
    assert payload["run_id"] == "run-42"
    assert payload["source"] == "tushare"
    assert payload["rows"] == 120


def test_logger_does_not_duplicate_after_reconfigure(capsys) -> None:
    configure_logging(level="INFO", fmt="one %(message)s", use_color=False, from_env=False)
    configure_logging(force=True, level="INFO", fmt="two %(message)s", use_color=False, from_env=False)
    get_logger("once").info("hello")
    lines = [line for line in capsys.readouterr().err.splitlines() if "hello" in line]
    assert len(lines) == 1
    assert lines[0].startswith("two ")


def test_named_logger_level(capsys) -> None:
    from darwin_logger import set_logger_level

    configure_logging(level="INFO", fmt="%(message)s", use_color=False, from_env=False)
    set_logger_level("noisy", logging.WARNING)
    logger = get_logger("noisy")
    logger.info("hidden")
    logger.warning("shown")
    captured = capsys.readouterr()
    assert "hidden" not in captured.err
    assert "shown" in captured.err
