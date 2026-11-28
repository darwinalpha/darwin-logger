"""darwin-logger: zero-dependency logging for Darwin CLI and data tools."""

from __future__ import annotations

from .context import bind_context, clear_context, get_context
from .core import (
    LoggingConfig,
    configure_logging,
    config_from_env,
    get_logger,
    get_logger_config,
    get_logging_config,
    is_configured,
    normalize_level,
    reconfigure_logging,
    reset_logging,
    set_log_level,
    set_logger_level,
)
from .exceptions import (
    ConfigurationError,
    DarwinLoggerError,
    InvalidLevelError,
    SinkError,
)
from .formatters import ConsoleFormatter, JsonFormatter
from .sinks import RotationConfig

__version__ = "0.1.1"

__all__ = [
    "__version__",
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
]
