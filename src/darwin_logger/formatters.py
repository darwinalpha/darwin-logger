"""Console and JSON formatters for darwin-logger."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, IO, Mapping

from .context import get_context

RESET = "\033[0m"
BOLD = "\033[1m"

_COLORS = {
    "CYAN": "\033[36m",
    "GREEN": "\033[32m",
    "YELLOW": "\033[33m",
    "RED": "\033[31m",
    "BG_RED": "\033[41m",
    "WHITE": "\033[37m",
}

LEVEL_COLORS: dict[int, str] = {
    logging.DEBUG: _COLORS["CYAN"],
    logging.INFO: _COLORS["GREEN"],
    logging.WARNING: _COLORS["YELLOW"],
    logging.ERROR: _COLORS["RED"],
    logging.CRITICAL: _COLORS["BG_RED"] + _COLORS["WHITE"] + BOLD,
}

DEFAULT_TEXT_FORMAT = "%(log_color)s%(asctime)s [%(levelname)s] %(name)s%(reset)s: %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off", ""}

_STANDARD_RECORD_KEYS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename", "module",
    "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs",
    "relativeCreated", "thread", "threadName", "processName", "process", "taskName",
    "message", "asctime", "log_color", "reset",
}

_RESERVED_JSON_KEYS = {"@timestamp", "level", "logger", "message", "exception", "stack", "service", "env"}


def _env(name: str) -> str | None:
    return os.environ.get(name)


def should_use_color(stream: IO[str] | None = None, explicit: bool | None = None) -> bool:
    """Resolve color usage: explicit > NO_COLOR > FORCE_COLOR > DARWIN_COLOR > TTY."""
    if explicit is not None:
        return bool(explicit)
    if _env("NO_COLOR") is not None:
        return False
    force = _env("FORCE_COLOR")
    if force is not None:
        return force.strip().lower() in _TRUE
    darwin = _env("DARWIN_COLOR")
    if darwin is not None:
        return darwin.strip().lower() in _TRUE
    target = stream if stream is not None else sys.stderr
    isatty = getattr(target, "isatty", None)
    return bool(isatty and isatty())


def _extra_fields(record: logging.LogRecord) -> dict[str, Any]:
    return {key: value for key, value in record.__dict__.items() if key not in _STANDARD_RECORD_KEYS}


class ConsoleFormatter(logging.Formatter):
    """Human-readable formatter with placeholder-based colors.

    Custom formats may use ``%(log_color)s`` and ``%(reset)s``. When colors are
    disabled these placeholders expand to empty strings, so the same format
    works in both interactive and redirected output.
    """

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        *,
        use_color: bool | None = None,
        stream: IO[str] | None = None,
    ) -> None:
        super().__init__(fmt if fmt is not None else DEFAULT_TEXT_FORMAT, datefmt)
        self.use_color = should_use_color(stream, use_color)

    def format(self, record: logging.LogRecord) -> str:
        color = LEVEL_COLORS.get(record.levelno, "") if self.use_color else ""
        reset = RESET if self.use_color else ""
        had_color = hasattr(record, "log_color")
        had_reset = hasattr(record, "reset")
        old_color = getattr(record, "log_color", None)
        old_reset = getattr(record, "reset", None)
        record.log_color = color
        record.reset = reset
        try:
            text = super().format(record)
        finally:
            if had_color:
                record.log_color = old_color
            else:
                delattr(record, "log_color")
            if had_reset:
                record.reset = old_reset
            else:
                delattr(record, "reset")
        context = get_context()
        if context:
            text += " " + " ".join(f"{key}={value}" for key, value in context.items())
        return text


class JsonFormatter(logging.Formatter):
    """Single-line JSON formatter for ELK, Loki and Datadog ingestion."""

    def __init__(
        self,
        *,
        service: str | None = None,
        env: str | None = None,
        fixed_fields: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self.service = service
        self.env = env
        self.fixed_fields = dict(fixed_fields or {})

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc)
        payload: dict[str, Any] = {
            "@timestamp": timestamp.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if self.service:
            payload["service"] = self.service
        if self.env:
            payload["env"] = self.env
        for key, value in self.fixed_fields.items():
            payload.setdefault(key, value)
        for key, value in get_context().items():
            payload.setdefault(key, value)
        for key, value in _extra_fields(record).items():
            if key not in _RESERVED_JSON_KEYS:
                payload.setdefault(key, value)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, ensure_ascii=False, default=str)
