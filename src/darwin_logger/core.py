"""Configuration state and public setup API for darwin-logger."""

from __future__ import annotations

import logging
import os
import re
import sys
import threading
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping

from .exceptions import ConfigurationError, InvalidLevelError
from .formatters import DEFAULT_DATE_FORMAT, DEFAULT_TEXT_FORMAT, ConsoleFormatter, JsonFormatter
from .sinks import RotationConfig, create_console_handler, create_file_handler

_UNSET = object()
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off", ""}
_SIZE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(b|kb|mb|gb)?\s*$", re.IGNORECASE)
_VALID_WHEN = {"S", "M", "H", "D", "W0", "W1", "W2", "W3", "W4", "W5", "W6", "MIDNIGHT"}


@dataclass(frozen=True)
class LoggingConfig:
    """Immutable snapshot of the active logging setup."""

    level: int = logging.INFO
    fmt: str = DEFAULT_TEXT_FORMAT
    datefmt: str = DEFAULT_DATE_FORMAT
    json: bool = False
    use_color: bool | None = None
    stderr: bool = True
    file: str | None = None
    rotation: RotationConfig | None = None
    service: str | None = None
    env: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return asdict(self)


@dataclass
class _State:
    config: LoggingConfig | None = None
    handlers: list[logging.Handler] = field(default_factory=list)
    displaced_handlers: list[logging.Handler] = field(default_factory=list)
    previous_root_level: int = logging.NOTSET
    logger_levels: dict[str, int] = field(default_factory=dict)


_LOCK = threading.RLock()
_STATE = _State()


def normalize_level(level: int | str) -> int:
    """Convert a level name or number to an integer, raising on invalid input."""
    if isinstance(level, bool):
        raise InvalidLevelError(f"Invalid log level: {level!r}")
    if isinstance(level, int):
        if level < 0:
            raise InvalidLevelError(f"Invalid log level: {level!r}")
        return level
    if isinstance(level, str):
        name = level.strip().upper()
        value = getattr(logging, name, None)
        if not isinstance(value, int):
            looked_up = logging.getLevelName(name)
            value = looked_up if isinstance(looked_up, int) else None
        if isinstance(value, int):
            return value
    raise InvalidLevelError(f"Invalid log level: {level!r}")


def _parse_bool(name: str, raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ConfigurationError(f"{name} must be one of: {', '.join(sorted(_TRUE | _FALSE))}")


def _parse_size(raw: str) -> int:
    match = _SIZE_RE.match(raw)
    if not match:
        raise ConfigurationError(f"Invalid size value: {raw!r}")
    number = float(match.group(1))
    unit = (match.group(2) or "b").lower()
    multipliers = {"b": 1, "kb": 1024, "mb": 1024 ** 2, "gb": 1024 ** 3}
    return int(number * multipliers[unit])


def _parse_int(name: str, raw: str, default: int) -> int:
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer, got {raw!r}") from exc


def _rotation_from_env() -> RotationConfig | None:
    kind = (os.environ.get("LOG_ROTATE") or "").strip().lower()
    if kind in {"", "none", "off", "false", "0"}:
        return None
    if kind not in {"size", "time"}:
        raise ConfigurationError("LOG_ROTATE must be 'size', 'time', or empty")
    backup_count = _parse_int("LOG_BACKUP_COUNT", os.environ.get("LOG_BACKUP_COUNT", "5"), 5)
    if kind == "size":
        max_bytes = _parse_size(os.environ.get("LOG_MAX_BYTES", "10MB"))
        if max_bytes <= 0:
            raise ConfigurationError("LOG_MAX_BYTES must be greater than zero")
        return RotationConfig(kind="size", max_bytes=max_bytes, backup_count=backup_count)
    when = (os.environ.get("LOG_ROTATE_WHEN", "midnight") or "midnight").strip().upper()
    if when not in _VALID_WHEN:
        raise ConfigurationError(f"Invalid LOG_ROTATE_WHEN: {when!r}")
    interval = _parse_int("LOG_ROTATE_INTERVAL", os.environ.get("LOG_ROTATE_INTERVAL", "1"), 1)
    if interval <= 0:
        raise ConfigurationError("LOG_ROTATE_INTERVAL must be greater than zero")
    return RotationConfig(kind="time", backup_count=backup_count, when=when, interval=interval)


def config_from_env() -> LoggingConfig:
    """Build a configuration from environment variables."""
    return LoggingConfig(
        level=normalize_level(os.environ.get("LOG_LEVEL", "INFO")),
        fmt=os.environ.get("LOG_FORMAT", DEFAULT_TEXT_FORMAT),
        datefmt=os.environ.get("LOG_DATE_FORMAT", DEFAULT_DATE_FORMAT),
        json=_parse_bool("LOG_JSON", os.environ.get("LOG_JSON"), False),
        stderr=_parse_bool("LOG_STDERR", os.environ.get("LOG_STDERR"), True),
        file=os.environ.get("LOG_FILE") or None,
        rotation=_rotation_from_env(),
        service=os.environ.get("LOG_SERVICE") or None,
        env=os.environ.get("LOG_ENV") or None,
    )


def _formatter_for(config: LoggingConfig, stream: Any) -> logging.Formatter:
    if config.json:
        return JsonFormatter(service=config.service, env=config.env)
    return ConsoleFormatter(config.fmt, config.datefmt, use_color=config.use_color, stream=stream)


def _remove_owned_handlers() -> None:
    for handler in _STATE.handlers:
        if handler in logging.root.handlers:
            logging.root.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
    _STATE.handlers = []
    for handler in _STATE.displaced_handlers:
        if handler not in logging.root.handlers:
            logging.root.addHandler(handler)
    _STATE.displaced_handlers = []


def _install(config: LoggingConfig, replace_existing: bool) -> None:
    if _STATE.config is None:
        _STATE.previous_root_level = logging.root.level
    _remove_owned_handlers()

    if replace_existing:
        for handler in list(logging.root.handlers):
            logging.root.removeHandler(handler)
            _STATE.displaced_handlers.append(handler)

    handlers: list[logging.Handler] = []
    if config.stderr:
        handlers.append(create_console_handler(sys.stderr, _formatter_for(config, sys.stderr)))
    if config.file:
        file_formatter = (
            JsonFormatter(service=config.service, env=config.env)
            if config.json
            else logging.Formatter(config.fmt, config.datefmt)
        )
        handlers.append(create_file_handler(Path(config.file), config.rotation))
        handlers[-1].setFormatter(file_formatter)

    for handler in handlers:
        logging.root.addHandler(handler)
    logging.root.setLevel(config.level)
    _STATE.handlers = handlers
    _STATE.config = config


def configure_logging(
    *,
    level: int | str | object = _UNSET,
    fmt: str | object = _UNSET,
    datefmt: str | object = _UNSET,
    json: bool | object = _UNSET,
    use_color: bool | None | object = _UNSET,
    stderr: bool | object = _UNSET,
    file: str | Path | None | object = _UNSET,
    rotation: RotationConfig | None | object = _UNSET,
    service: str | None | object = _UNSET,
    env: str | None | object = _UNSET,
    from_env: bool = True,
    force: bool = False,
    replace_existing: bool = False,
) -> LoggingConfig:
    """Configure the root logger once, or rebuild it with ``force=True``.

    Explicit keyword arguments override environment variables. Without
    ``force``, an existing configuration is returned unchanged; this makes the
    function safe to call from multiple modules without partial updates.
    """
    with _LOCK:
        if _STATE.config is not None and not force:
            return _STATE.config

        config = config_from_env() if from_env else LoggingConfig()
        overrides: dict[str, Any] = {}
        supplied = {
            "level": level, "fmt": fmt, "datefmt": datefmt, "json": json,
            "use_color": use_color, "stderr": stderr, "file": file,
            "rotation": rotation, "service": service, "env": env,
        }
        for key, value in supplied.items():
            if value is not _UNSET:
                overrides[key] = value

        if "level" in overrides:
            overrides["level"] = normalize_level(overrides["level"])
        if "json" in overrides and not isinstance(overrides["json"], bool):
            overrides["json"] = _parse_bool("json", str(overrides["json"]), False)
        if "use_color" in overrides and overrides["use_color"] is not None:
            overrides["use_color"] = _parse_bool("use_color", str(overrides["use_color"]), False)
        if "stderr" in overrides and not isinstance(overrides["stderr"], bool):
            overrides["stderr"] = _parse_bool("stderr", str(overrides["stderr"]), True)
        if "file" in overrides:
            overrides["file"] = str(overrides["file"]) if overrides["file"] else None
        if "rotation" in overrides and overrides["rotation"] is not None:
            if not isinstance(overrides["rotation"], RotationConfig):
                raise ConfigurationError("rotation must be a RotationConfig instance")

        config = replace(config, **overrides)
        _install(config, replace_existing)
        return config


def reconfigure_logging(**kwargs: Any) -> LoggingConfig:
    """Rebuild the logging setup, closing handlers owned by this library."""
    return configure_logging(force=True, **kwargs)


def reset_logging() -> None:
    """Restore the root logger and named logger levels to their pre-setup state."""
    with _LOCK:
        _remove_owned_handlers()
        logging.root.setLevel(_STATE.previous_root_level)
        for name, level in _STATE.logger_levels.items():
            logging.getLogger(name).setLevel(level)
        _STATE.logger_levels.clear()
        _STATE.config = None


def is_configured() -> bool:
    """Return whether darwin-logger currently owns a root setup."""
    return _STATE.config is not None


def get_logger(name: str = "") -> logging.Logger:
    """Return a standard logger. This function has no configuration side effects."""
    return logging.getLogger(name)


def set_log_level(level: int | str) -> None:
    """Change the root level at runtime."""
    value = normalize_level(level)
    with _LOCK:
        logging.root.setLevel(value)
        if _STATE.config is not None:
            _STATE.config = replace(_STATE.config, level=value)


def set_logger_level(name: str, level: int | str) -> None:
    """Change one named logger's level; reset_logging() restores it."""
    value = normalize_level(level)
    with _LOCK:
        target = logging.getLogger(name)
        if name not in _STATE.logger_levels:
            _STATE.logger_levels[name] = target.level
        target.setLevel(value)


def get_logging_config() -> dict[str, Any]:
    """Return a snapshot of the active setup."""
    with _LOCK:
        result: dict[str, Any] = {
            "configured": _STATE.config is not None,
            "root_level": logging.getLevelName(logging.root.level),
            "handlers": [
                {
                    "type": type(handler).__name__,
                    "formatter": type(handler.formatter).__name__ if handler.formatter else None,
                }
                for handler in _STATE.handlers
            ],
            "config": _STATE.config.to_dict() if _STATE.config else None,
        }
        return result


def get_logger_config(name: str) -> dict[str, Any]:
    """Return a snapshot of a named logger."""
    target = logging.getLogger(name)
    return {
        "name": target.name,
        "level": logging.getLevelName(target.level),
        "effective_level": logging.getLevelName(target.getEffectiveLevel()),
        "handlers": [type(handler).__name__ for handler in target.handlers],
        "propagate": target.propagate,
    }
