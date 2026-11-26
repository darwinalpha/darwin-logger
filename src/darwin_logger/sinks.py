"""Handler factories for darwin-logger."""

from __future__ import annotations

import logging
import logging.handlers
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Literal

from .exceptions import SinkError

RotationKind = Literal["size", "time"]


@dataclass(frozen=True)
class RotationConfig:
    """File rotation policy.

    ``kind`` is ``"size"`` or ``"time"``; a falsy kind means no rotation.
    """

    kind: RotationKind | None = None
    max_bytes: int = 0
    backup_count: int = 0
    when: str = "midnight"
    interval: int = 1


def create_console_handler(stream: IO[str], formatter: logging.Formatter) -> logging.StreamHandler:
    """Create a stderr/stdout handler."""
    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)
    return handler


def create_file_handler(path: str | Path, rotation: RotationConfig | None = None) -> logging.Handler:
    """Create a UTF-8 file handler, optionally with rotation.

    The parent directory is created automatically. The caller owns the handler
    and should close it when replacing the logging setup.
    """
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if rotation is None or not rotation.kind:
            return logging.FileHandler(target, encoding="utf-8")
        if rotation.kind == "size":
            if rotation.max_bytes <= 0:
                raise SinkError("size rotation requires max_bytes > 0")
            return logging.handlers.RotatingFileHandler(
                target,
                maxBytes=rotation.max_bytes,
                backupCount=rotation.backup_count,
                encoding="utf-8",
            )
        if rotation.kind == "time":
            return logging.handlers.TimedRotatingFileHandler(
                target,
                when=rotation.when,
                interval=rotation.interval,
                backupCount=rotation.backup_count,
                encoding="utf-8",
            )
        raise SinkError(f"Unknown rotation kind: {rotation.kind!r}")
    except SinkError:
        raise
    except OSError as exc:
        raise SinkError(f"Cannot create file sink {target}: {exc}") from exc
