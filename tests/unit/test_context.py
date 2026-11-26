"""Unit tests for context variable helpers."""

from __future__ import annotations

from darwin_logger import bind_context, clear_context, get_context


def test_bind_and_clear() -> None:
    assert get_context() == {}
    token = bind_context(run_id="r1")
    assert get_context() == {"run_id": "r1"}
    clear_context(token)
    assert get_context() == {}


def test_nested_bind() -> None:
    outer = bind_context(run_id="r1")
    inner = bind_context(source="tushare", run_id="r2")
    assert get_context() == {"run_id": "r2", "source": "tushare"}
    clear_context(inner)
    assert get_context() == {"run_id": "r1"}
    clear_context(outer)
    assert get_context() == {}


def test_clear_without_token() -> None:
    bind_context(run_id="r1")
    clear_context()
    assert get_context() == {}
