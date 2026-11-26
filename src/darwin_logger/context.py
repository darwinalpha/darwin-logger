"""Context variables shared by log formatters."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

_CONTEXT: ContextVar[dict[str, Any]] = ContextVar("darwin_logger_context", default={})


def get_context() -> dict[str, Any]:
    """Return a copy of the current context fields."""
    return dict(_CONTEXT.get())


def bind_context(**fields: Any) -> Token:
    """Bind fields to the current context and return a reset token."""
    payload = dict(_CONTEXT.get())
    payload.update(fields)
    return _CONTEXT.set(payload)


def clear_context(token: Token | None = None) -> None:
    """Reset a previously bound context, or clear it completely."""
    if token is None:
        _CONTEXT.set({})
    else:
        _CONTEXT.reset(token)
