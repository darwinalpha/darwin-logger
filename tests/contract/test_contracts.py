"""Contract tests: dependency-free core, stable exports, bilingual docs."""

from __future__ import annotations

import re
from pathlib import Path

import darwin_logger

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "darwin_logger"

FORBIDDEN_IMPORTS = (
    "darwin_common",
    "dotenv",
    "pydantic",
    "pandas",
    "pyarrow",
    "colorama",
    "yaml",
)

EXPECTED_EXPORTS = {
    "LoggingConfig",
    "RotationConfig",
    "configure_logging",
    "reconfigure_logging",
    "reset_logging",
    "is_configured",
    "config_from_env",
    "get_logger",
    "set_log_level",
    "set_logger_level",
    "get_logging_config",
    "get_logger_config",
    "bind_context",
    "clear_context",
    "get_context",
    "normalize_level",
    "ConsoleFormatter",
    "JsonFormatter",
    "DarwinLoggerError",
    "ConfigurationError",
    "InvalidLevelError",
    "SinkError",
}


def test_core_has_no_forbidden_imports() -> None:
    for path in SRC.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for module in FORBIDDEN_IMPORTS:
            assert f"import {module}" not in source
            assert f"from {module}" not in source


def test_public_exports_are_available() -> None:
    assert EXPECTED_EXPORTS.issubset(set(darwin_logger.__all__))
    for name in EXPECTED_EXPORTS:
        assert hasattr(darwin_logger, name)


def test_removed_legacy_symbols_are_absent() -> None:
    assert not hasattr(darwin_logger, "setup_logger")


def test_english_docs_have_no_chinese_except_language_switch() -> None:
    han = re.compile(r"[\u4e00-\u9fff]")
    targets = [
        ROOT / "README.md",
        ROOT / "docs" / "development-guide.md",
        ROOT / "examples" / "README.md",
    ]
    for path in targets:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "简体中文" in line:
                continue
            assert not han.search(line), f"Chinese text in {path.name}:{number}"


def test_chinese_docs_exist() -> None:
    for path in (
        ROOT / "README.cn.md",
        ROOT / "docs" / "development-guide.cn.md",
        ROOT / "examples" / "README.cn.md",
    ):
        assert path.exists()
