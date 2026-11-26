"""Exceptions raised by :mod:`darwin_logger`."""

from __future__ import annotations


class DarwinLoggerError(Exception):
    """Base class for all darwin-logger errors."""


class ConfigurationError(DarwinLoggerError):
    """Raised when logging configuration is invalid."""


class InvalidLevelError(ConfigurationError):
    """Raised when a log level cannot be understood."""


class SinkError(ConfigurationError):
    """Raised when a log sink cannot be created."""
