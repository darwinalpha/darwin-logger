"""Integration tests for file sinks and rotation."""

from __future__ import annotations

import json

from darwin_logger import configure_logging, get_logger, reconfigure_logging, reset_logging
from darwin_logger.core import _STATE
from darwin_logger.sinks import RotationConfig


def test_text_file_output(tmp_path) -> None:
    target = tmp_path / "logs" / "app.log"
    configure_logging(
        level="INFO",
        fmt="%(levelname)s %(message)s",
        file=target,
        stderr=False,
        from_env=False,
    )
    get_logger("file").info("persisted")
    assert "INFO persisted" in target.read_text(encoding="utf-8")


def test_json_file_output(tmp_path) -> None:
    target = tmp_path / "app.jsonl"
    configure_logging(level="INFO", json=True, file=target, stderr=False, from_env=False)
    get_logger("json").warning("persisted")
    payload = json.loads(target.read_text(encoding="utf-8").strip())
    assert payload["level"] == "WARNING"
    assert payload["message"] == "persisted"


def test_size_rotation_creates_backup(tmp_path) -> None:
    target = tmp_path / "rotated.log"
    rotation = RotationConfig(kind="size", max_bytes=120, backup_count=2)
    configure_logging(
        level="INFO",
        fmt="%(message)s",
        file=target,
        rotation=rotation,
        stderr=False,
        from_env=False,
    )
    logger = get_logger("rotate")
    for index in range(30):
        logger.info("message-%03d-payload", index)
    assert target.exists()
    assert (tmp_path / "rotated.log.1").exists()


def test_reconfigure_closes_old_file_handler(tmp_path) -> None:
    first = tmp_path / "first.log"
    second = tmp_path / "second.log"
    configure_logging(level="INFO", fmt="%(message)s", file=first, stderr=False, from_env=False)
    old_handler = _STATE.handlers[0]
    reconfigure_logging(level="INFO", fmt="%(message)s", file=second, stderr=False, from_env=False)
    assert old_handler not in _STATE.handlers
    get_logger("switch").info("new")
    assert first.read_text(encoding="utf-8") == ""
    assert "new" in second.read_text(encoding="utf-8")


def test_reset_restores_root_level(tmp_path) -> None:
    from darwin_logger import is_configured

    original = __import__("logging").root.level
    configure_logging(level="CRITICAL", file=tmp_path / "x.log", stderr=False, from_env=False)
    assert is_configured()
    reset_logging()
    assert not is_configured()
    assert __import__("logging").root.level == original
