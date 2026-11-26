"""Unit tests for console and JSON formatters."""

from __future__ import annotations

import io
import json
import logging
import sys

from darwin_logger.context import bind_context, clear_context
from darwin_logger.formatters import (
    ConsoleFormatter,
    JsonFormatter,
    should_use_color,
)


def make_record(
    level: int = logging.INFO,
    message: str = "hello",
    name: str = "demo",
    **extra: object,
) -> logging.LogRecord:
    record = logging.LogRecord(name, level, __file__, 1, message, (), None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


class TestColorResolution:
    def test_explicit_true(self, monkeypatch) -> None:
        monkeypatch.setenv("NO_COLOR", "1")
        assert should_use_color(explicit=True) is True

    def test_no_color_wins(self, monkeypatch) -> None:
        monkeypatch.setenv("NO_COLOR", "")
        monkeypatch.setenv("FORCE_COLOR", "1")
        assert should_use_color() is False

    def test_force_color(self, monkeypatch) -> None:
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.setenv("FORCE_COLOR", "yes")
        assert should_use_color() is True

    def test_darwin_color(self, monkeypatch) -> None:
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("FORCE_COLOR", raising=False)
        monkeypatch.setenv("DARWIN_COLOR", "on")
        assert should_use_color() is True
        monkeypatch.setenv("DARWIN_COLOR", "0")
        assert should_use_color() is False

    def test_non_tty_defaults_off(self, monkeypatch) -> None:
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("FORCE_COLOR", raising=False)
        monkeypatch.delenv("DARWIN_COLOR", raising=False)
        assert should_use_color(io.StringIO()) is False


class TestConsoleFormatter:
    def test_colored_output(self) -> None:
        formatter = ConsoleFormatter("%(log_color)s%(levelname)s%(reset)s %(message)s", use_color=True)
        text = formatter.format(make_record())
        assert "\033[32m" in text
        assert "\033[0m" in text
        assert "hello" in text

    def test_plain_output(self) -> None:
        formatter = ConsoleFormatter("%(log_color)s%(levelname)s%(reset)s %(message)s", use_color=False)
        text = formatter.format(make_record())
        assert "\033[" not in text
        assert text == "INFO hello"

    def test_custom_format_without_placeholders(self) -> None:
        formatter = ConsoleFormatter("%(name)s: %(message)s", use_color=True)
        assert formatter.format(make_record()) == "demo: hello"

    def test_level_colors(self) -> None:
        formatter = ConsoleFormatter("%(log_color)s%(levelname)s%(reset)s", use_color=True)
        assert "\033[36m" in formatter.format(make_record(logging.DEBUG))
        assert "\033[31m" in formatter.format(make_record(logging.ERROR))
        assert "\033[41m" in formatter.format(make_record(logging.CRITICAL))

    def test_record_attributes_are_cleaned(self) -> None:
        record = make_record()
        ConsoleFormatter(use_color=True).format(record)
        assert not hasattr(record, "log_color")
        assert not hasattr(record, "reset")

    def test_context_is_appended(self) -> None:
        token = bind_context(run_id="r1", source="tushare")
        try:
            text = ConsoleFormatter("%(message)s", use_color=False).format(make_record())
        finally:
            clear_context(token)
        assert "run_id=r1" in text
        assert "source=tushare" in text


class TestJsonFormatter:
    def test_required_fields(self) -> None:
        payload = json.loads(JsonFormatter().format(make_record()))
        assert payload["@timestamp"].endswith("Z")
        assert payload["level"] == "INFO"
        assert payload["logger"] == "demo"
        assert payload["message"] == "hello"

    def test_service_env_and_fixed_fields(self) -> None:
        formatter = JsonFormatter(service="fetch", env="prod", fixed_fields={"team": "data"})
        payload = json.loads(formatter.format(make_record()))
        assert payload["service"] == "fetch"
        assert payload["env"] == "prod"
        assert payload["team"] == "data"

    def test_context_and_extra(self) -> None:
        token = bind_context(run_id="r2")
        try:
            payload = json.loads(
                JsonFormatter().format(make_record(task="daily", levelno_reserved="x"))
            )
        finally:
            clear_context(token)
        assert payload["run_id"] == "r2"
        assert payload["task"] == "daily"
        assert payload["levelno_reserved"] == "x"

    def test_reserved_extra_cannot_override(self) -> None:
        record = logging.LogRecord("demo", logging.INFO, __file__, 1, "hello", (), None)
        record.message = "override"
        payload = json.loads(JsonFormatter().format(record))
        assert payload["message"] == "hello"

    def test_exception_is_serialized(self) -> None:
        try:
            raise ValueError("boom")
        except ValueError:
            record = logging.LogRecord(
                "demo", logging.ERROR, __file__, 1, "failed", (), sys.exc_info()
            )
        payload = json.loads(JsonFormatter().format(record))
        assert "ValueError: boom" in payload["exception"]

    def test_non_serializable_value(self) -> None:
        payload = json.loads(JsonFormatter().format(make_record(obj=object())))
        assert isinstance(payload["obj"], str)
