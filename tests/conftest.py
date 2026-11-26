"""Shared fixtures for darwin-logger tests."""

from __future__ import annotations

import logging
import os
from typing import Generator

import pytest

from darwin_logger import reset_logging

ENV_KEYS = [
    "LOG_LEVEL",
    "LOG_FORMAT",
    "LOG_DATE_FORMAT",
    "LOG_JSON",
    "LOG_STDERR",
    "LOG_FILE",
    "LOG_ROTATE",
    "LOG_MAX_BYTES",
    "LOG_BACKUP_COUNT",
    "LOG_ROTATE_WHEN",
    "LOG_ROTATE_INTERVAL",
    "LOG_SERVICE",
    "LOG_ENV",
    "NO_COLOR",
    "FORCE_COLOR",
    "DARWIN_COLOR",
]


@pytest.fixture(autouse=True)
def clean_logging() -> Generator[None, None, None]:
    reset_logging()
    yield
    reset_logging()


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
    saved = {key: os.environ.pop(key, None) for key in ENV_KEYS}
    yield
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
