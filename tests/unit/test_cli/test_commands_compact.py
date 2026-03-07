"""Tests for /compact command — Task 161."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from lidco.cli.commands import CommandRegistry


def _run(coro) -> str:
    return asyncio.run(coro)


def _make_registry_with_history(history: list[dict]) -> CommandRegistry:
    reg = CommandRegistry()
    session = MagicMock()
    orch = MagicMock()
    orch._conversation_history = history
    session.orchestrator = orch
    reg.set_session(session)
    return reg


# ── /compact registered ───────────────────────────────────────────────────────

class TestCompactRegistered:
    def test_command_exists(self):
        reg = CommandRegistry()
        assert reg.get("compact") is not None

    def test_no_session_returns_message(self):
        reg = CommandRegistry()
        result = _run(reg.get("compact").handler())
        assert isinstance(result, str)
        assert len(result) > 0


# ── /compact with history ─────────────────────────────────────────────────────

class TestCompactWithHistory:
    def _make_history(self, n: int) -> list[dict]:
        return [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"}
            for i in range(n)
        ]

    def test_compacts_long_history(self):
        history = self._make_history(20)
        reg = _make_registry_with_history(history)
        result = _run(reg.get("compact").handler())
        assert "удалено" in result or "оставлено" in result

    def test_calls_restore_history(self):
        history = self._make_history(20)
        reg = _make_registry_with_history(history)
        _run(reg.get("compact").handler())
        orch = reg._session.orchestrator
        orch.restore_history.assert_called_once()

    def test_keeps_last_6_by_default(self):
        history = self._make_history(20)
        reg = _make_registry_with_history(history)
        _run(reg.get("compact").handler())
        orch = reg._session.orchestrator
        kept = orch.restore_history.call_args[0][0]
        assert len(kept) == 6

    def test_custom_keep_count(self):
        history = self._make_history(20)
        reg = _make_registry_with_history(history)
        _run(reg.get("compact").handler(arg="10"))
        orch = reg._session.orchestrator
        kept = orch.restore_history.call_args[0][0]
        assert len(kept) == 10

    def test_short_history_no_compact(self):
        history = self._make_history(4)
        reg = _make_registry_with_history(history)
        result = _run(reg.get("compact").handler())
        assert "уже короткая" in result or "нечего" in result.lower()
        # restore_history should not be called
        orch = reg._session.orchestrator
        orch.restore_history.assert_not_called()

    def test_empty_history_no_compact(self):
        reg = _make_registry_with_history([])
        result = _run(reg.get("compact").handler())
        assert isinstance(result, str)

    def test_invalid_arg_returns_error(self):
        reg = _make_registry_with_history(self._make_history(20))
        result = _run(reg.get("compact").handler(arg="abc"))
        assert "неверный" in result.lower() or "invalid" in result.lower() or "аргумент" in result.lower()

    def test_result_shows_counts(self):
        history = self._make_history(20)
        reg = _make_registry_with_history(history)
        result = _run(reg.get("compact").handler())
        # Should mention numbers of removed/kept messages
        assert any(char.isdigit() for char in result)

    def test_keeps_last_n_messages(self):
        history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"}
                   for i in range(10)]
        reg = _make_registry_with_history(history)
        _run(reg.get("compact").handler(arg="4"))
        orch = reg._session.orchestrator
        kept = orch.restore_history.call_args[0][0]
        # Should be the LAST 4 messages
        assert kept == history[-4:]

    def test_keep_min_2(self):
        history = self._make_history(10)
        reg = _make_registry_with_history(history)
        _run(reg.get("compact").handler(arg="1"))  # should clamp to 2
        orch = reg._session.orchestrator
        kept = orch.restore_history.call_args[0][0]
        assert len(kept) == 2
