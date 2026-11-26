"""Unit tests for configuration state and public API."""

from __future__ import annotations

import logging

import pytest

from darwin_logger import (
    ConfigurationError,
    InvalidLevelError,
    LoggingConfig,
    RotationConfig,
    configure_logging,
    config_from_env,
    get_logger,
    get_logging_config,
    is_configured,
    normalize_level,
    reconfigure_logging,
    reset_logging,
    set_log_level,
    set_logger_level,
)
from darwin_logger.core import _STATE


class TestNormalizeLevel:
    def test_int_level(self) -> None:
        assert normalize_level(logging.DEBUG) == logging.DEBUG

    def test_string_level(self) -> None:
        assert normalize_level("warning") == logging.WARNING

    def test_numeric_string_is_not_supported(self) -> None:
        with pytest.raises(InvalidLevelError):
            normalize_level("10")

    def test_invalid_name(self) -> None:
        with pytest.raises(InvalidLevelError):
            normalize_level("verbose")

    def test_bool_and_negative(self) -> None:
        with pytest.raises(InvalidLevelError):
            normalize_level(True)
        with pytest.raises(InvalidLevelError):
            normalize_level(-1)

    def test_registered_custom_level(self) -> None:
        logging.addLevelName(15, "NOTICE")
        assert normalize_level("notice") == 15


class TestConfigureLogging:
    def test_explicit_config(self, clean_env: None) -> None:
        config = configure_logging(
            level="DEBUG", fmt="%(message)s", datefmt="%H:%M", use_color=False, from_env=False
        )
        assert config.level == logging.DEBUG
        assert config.fmt == "%(message)s"
        assert config.datefmt == "%H:%M"
        assert is_configured()

    def test_idempotent_without_force(self) -> None:
        first = configure_logging(level="INFO", fmt="first %(message)s", from_env=False)
        second = configure_logging(level="DEBUG", fmt="second %(message)s", from_env=False)
        assert second is first
        assert logging.root.level == logging.INFO
        assert len(_STATE.handlers) == 1

    def test_reconfigure_rebuilds_handlers(self) -> None:
        first = configure_logging(level="INFO", from_env=False)
        first_handler = _STATE.handlers[0]
        second = reconfigure_logging(level="DEBUG", fmt="%(message)s", from_env=False)
        assert second is not first
        assert first_handler not in logging.root.handlers
        assert logging.root.level == logging.DEBUG
        assert _STATE.handlers[0] is not first_handler

    def test_empty_format_is_respected(self) -> None:
        config = configure_logging(fmt="", from_env=False)
        assert config.fmt == ""

    def test_invalid_rotation_object(self) -> None:
        with pytest.raises(ConfigurationError):
            configure_logging(rotation="size", from_env=False)  # type: ignore[arg-type]

    def test_no_handlers_when_stderr_and_file_disabled(self) -> None:
        configure_logging(stderr=False, from_env=False)
        assert _STATE.handlers == []


class TestStateAndLevelChanges:
    def test_get_logger_has_no_side_effect(self) -> None:
        logger = get_logger("pure")
        assert isinstance(logger, logging.Logger)
        assert not is_configured()

    def test_set_level_does_not_mark_configured(self) -> None:
        set_log_level("DEBUG")
        assert logging.root.level == logging.DEBUG
        assert not is_configured()

    def test_set_level_updates_config_snapshot(self) -> None:
        configure_logging(level="INFO", from_env=False)
        set_log_level("ERROR")
        assert get_logging_config()["config"]["level"] == logging.ERROR

    def test_named_level_is_restored_on_reset(self) -> None:
        configure_logging(from_env=False)
        set_logger_level("restored", "DEBUG")
        assert get_logger("restored").level == logging.DEBUG
        reset_logging()
        assert get_logger("restored").level == logging.NOTSET

    def test_root_level_is_restored_on_reset(self) -> None:
        original = logging.root.level
        configure_logging(level="CRITICAL", from_env=False)
        reset_logging()
        assert logging.root.level == original
        assert not is_configured()


class TestEnvConfig:
    def test_defaults(self, clean_env: None) -> None:
        config = config_from_env()
        assert config.level == logging.INFO
        assert config.json is False
        assert config.stderr is True
        assert config.file is None
        assert config.rotation is None

    def test_basic_env(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_LEVEL", "debug")
        monkeypatch.setenv("LOG_JSON", "yes")
        monkeypatch.setenv("LOG_SERVICE", "fetch")
        monkeypatch.setenv("LOG_ENV", "prod")
        config = config_from_env()
        assert config.level == logging.DEBUG
        assert config.json is True
        assert config.service == "fetch"
        assert config.env == "prod"

    def test_invalid_level_raises(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_LEVEL", "DEUBG")
        with pytest.raises(InvalidLevelError):
            config_from_env()

    def test_invalid_bool_raises(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_JSON", "maybe")
        with pytest.raises(ConfigurationError):
            config_from_env()

    def test_size_rotation_env(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_ROTATE", "size")
        monkeypatch.setenv("LOG_MAX_BYTES", "2MB")
        monkeypatch.setenv("LOG_BACKUP_COUNT", "3")
        rotation = config_from_env().rotation
        assert rotation == RotationConfig(kind="size", max_bytes=2 * 1024 ** 2, backup_count=3)

    def test_time_rotation_env(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_ROTATE", "time")
        monkeypatch.setenv("LOG_ROTATE_WHEN", "midnight")
        monkeypatch.setenv("LOG_ROTATE_INTERVAL", "2")
        rotation = config_from_env().rotation
        assert rotation is not None
        assert rotation.kind == "time"
        assert rotation.when == "MIDNIGHT"
        assert rotation.interval == 2

    def test_bad_rotation_env(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_ROTATE", "daily")
        with pytest.raises(ConfigurationError):
            config_from_env()


class TestConfigSnapshot:
    def test_config_is_frozen(self) -> None:
        config = LoggingConfig()
        with pytest.raises(Exception):
            config.level = logging.DEBUG  # type: ignore[misc]

    def test_to_dict_is_serializable(self) -> None:
        data = configure_logging(rotation=RotationConfig(kind="size", max_bytes=10), from_env=False).to_dict()
        assert data["rotation"]["max_bytes"] == 10
