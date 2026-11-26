"""Unit tests for handler factories."""

from __future__ import annotations

import logging
import logging.handlers

import pytest

from darwin_logger.exceptions import SinkError
from darwin_logger.sinks import RotationConfig, create_file_handler


def test_plain_file_handler_creates_parent(tmp_path) -> None:
    target = tmp_path / "nested" / "app.log"
    handler = create_file_handler(target)
    try:
        assert isinstance(handler, logging.FileHandler)
        assert target.parent.is_dir()
    finally:
        handler.close()


def test_size_rotation_handler(tmp_path) -> None:
    handler = create_file_handler(
        tmp_path / "app.log", RotationConfig(kind="size", max_bytes=256, backup_count=2)
    )
    try:
        assert isinstance(handler, logging.handlers.RotatingFileHandler)
        assert handler.maxBytes == 256
        assert handler.backupCount == 2
    finally:
        handler.close()


def test_time_rotation_handler(tmp_path) -> None:
    handler = create_file_handler(
        tmp_path / "app.log", RotationConfig(kind="time", when="H", interval=2, backup_count=3)
    )
    try:
        assert isinstance(handler, logging.handlers.TimedRotatingFileHandler)
        assert handler.interval == 2 * 3600  # TimedRotatingFileHandler stores seconds for 'H'
        assert handler.backupCount == 3
    finally:
        handler.close()


def test_no_rotation_kind(tmp_path) -> None:
    handler = create_file_handler(tmp_path / "app.log", RotationConfig())
    try:
        assert type(handler) is logging.FileHandler
    finally:
        handler.close()


def test_invalid_size_rotation(tmp_path) -> None:
    with pytest.raises(SinkError):
        create_file_handler(tmp_path / "app.log", RotationConfig(kind="size", max_bytes=0))


def test_bad_parent_path(tmp_path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    with pytest.raises(SinkError):
        create_file_handler(blocker / "app.log")
