"""Tests for /history (#164) and /budget (#165) commands."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from lidco.cli.commands import CommandRegistry


def _run(coro) -> str:
    return asyncio.run(coro)


def _make_session(history: list[dict] | None = None, budget_total: int = 0,
                  budget_limit: int = 0, by_role: dict | None = None) -> MagicMock:
    session = MagicMock()
    orch = MagicMock()
    orch._conversation_history = history or []
    session.orchestrator = orch

    tb = MagicMock()
    tb.total_tokens = budget_total
    tb.session_limit = budget_limit
    tb._total_cost_usd = 0.0
    tb._by_role = by_role or {}
    session.token_budget = tb
    return session


def _make_registry(history=None, budget_total=0, budget_limit=0, by_role=None) -> CommandRegistry:
    reg = CommandRegistry()
    reg.set_session(_make_session(history, budget_total, budget_limit, by_role))
    return reg


def _history(n_turns: int) -> list[dict]:
    msgs = []
    for i in range(n_turns):
        msgs.append({"role": "user", "content": f"Вопрос {i + 1}: что делать?"})
        msgs.append({"role": "assistant", "content": f"Ответ {i + 1}: вот что нужно сделать."})
    return msgs


# ── /history — registered ─────────────────────────────────────────────────────

class TestHistoryCommand:
    def test_registered(self):
        reg = CommandRegistry()
        assert reg.get("history") is not None

    def test_no_session(self):
        reg = CommandRegistry()
        result = _run(reg.get("history").handler())
        assert isinstance(result, str)

    def test_empty_history(self):
        reg = _make_registry(history=[])
        result = _run(reg.get("history").handler())
        assert "пуста" in result.lower()

    def test_shows_turns(self):
        reg = _make_registry(history=_history(3))
        result = _run(reg.get("history").handler())
        assert "Ход" in result
        assert "Вопрос" in result

    def test_default_5_turns(self):
        reg = _make_registry(history=_history(10))
        result = _run(reg.get("history").handler())
        assert "5" in result  # shows last 5 of 10

    def test_custom_n(self):
        reg = _make_registry(history=_history(10))
        result = _run(reg.get("history").handler(arg="3"))
        assert "3" in result

    def test_invalid_arg(self):
        reg = _make_registry(history=_history(3))
        result = _run(reg.get("history").handler(arg="abc"))
        assert "неверный" in result.lower() or "invalid" in result.lower()

    def test_shows_user_message_preview(self):
        reg = _make_registry(history=_history(2))
        result = _run(reg.get("history").handler())
        assert "Вопрос" in result

    def test_shows_assistant_preview(self):
        reg = _make_registry(history=_history(2))
        result = _run(reg.get("history").handler())
        assert "Ответ" in result

    def test_mentions_compact(self):
        reg = _make_registry(history=_history(10))
        result = _run(reg.get("history").handler())
        assert "compact" in result.lower()

    def test_long_messages_truncated(self):
        long_msg = "x" * 300
        history = [
            {"role": "user", "content": long_msg},
            {"role": "assistant", "content": long_msg},
        ]
        reg = _make_registry(history=history)
        result = _run(reg.get("history").handler())
        assert "…" in result  # truncation indicator

    def test_n_1_returns_one_turn(self):
        reg = _make_registry(history=_history(5))
        result = _run(reg.get("history").handler(arg="1"))
        assert "Ход 5" in result


# ── /budget — registered ──────────────────────────────────────────────────────

class TestBudgetCommand:
    def test_registered(self):
        reg = CommandRegistry()
        assert reg.get("budget") is not None

    def test_no_session(self):
        reg = CommandRegistry()
        result = _run(reg.get("budget").handler())
        assert isinstance(result, str)

    def test_shows_total_tokens(self):
        reg = _make_registry(budget_total=5000)
        result = _run(reg.get("budget").handler())
        assert "5" in result  # 5.0k or 5000

    def test_unlimited_when_no_limit(self):
        reg = _make_registry(budget_total=0, budget_limit=0)
        result = _run(reg.get("budget").handler())
        assert "ограничен" in result.lower() or "unlimited" in result.lower()

    def test_shows_limit_when_set(self):
        reg = _make_registry(budget_total=1000, budget_limit=10000)
        result = _run(reg.get("budget").handler())
        assert "10" in result  # 10k or 10000

    def test_shows_progress_bar_when_limited(self):
        reg = _make_registry(budget_total=5000, budget_limit=10000)
        result = _run(reg.get("budget").handler())
        assert "█" in result or "░" in result

    def test_by_role_shown(self):
        reg = _make_registry(by_role={"coder": 3000, "tester": 1500})
        result = _run(reg.get("budget").handler())
        assert "coder" in result
        assert "tester" in result

    def test_set_limit(self):
        reg = CommandRegistry()
        session = _make_session()
        reg.set_session(session)
        result = _run(reg.get("budget").handler(arg="set 50000"))
        assert "50" in result or "лимит" in result.lower()

    def test_set_zero_removes_limit(self):
        reg = CommandRegistry()
        session = _make_session()
        reg.set_session(session)
        result = _run(reg.get("budget").handler(arg="set 0"))
        assert "снят" in result.lower() or "без ограничен" in result.lower()

    def test_set_invalid_arg(self):
        reg = CommandRegistry()
        session = _make_session()
        reg.set_session(session)
        result = _run(reg.get("budget").handler(arg="set xyz"))
        assert "неверн" in result.lower() or "invalid" in result.lower()

    def test_set_usage_no_n(self):
        reg = CommandRegistry()
        session = _make_session()
        reg.set_session(session)
        result = _run(reg.get("budget").handler(arg="set"))
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_shows_compact_hint(self):
        reg = _make_registry(budget_total=1000)
        result = _run(reg.get("budget").handler())
        assert "compact" in result.lower() or "set" in result.lower()


# ── Task 166: compact suggestion in suggestions ───────────────────────────────

class TestCompactSuggestion:
    def test_no_compact_when_short_history(self):
        from lidco.core.suggestions import suggest, COMPACT_SUGGEST_THRESHOLD
        hints = suggest([], history_len=COMPACT_SUGGEST_THRESHOLD - 1)
        combined = " ".join(hints)
        assert "compact" not in combined.lower()

    def test_compact_suggested_when_long_history(self):
        from lidco.core.suggestions import suggest, COMPACT_SUGGEST_THRESHOLD
        hints = suggest([], history_len=COMPACT_SUGGEST_THRESHOLD + 5)
        combined = " ".join(hints)
        assert "compact" in combined.lower()

    def test_compact_at_threshold(self):
        from lidco.core.suggestions import suggest, COMPACT_SUGGEST_THRESHOLD
        hints = suggest([], history_len=COMPACT_SUGGEST_THRESHOLD)
        combined = " ".join(hints)
        assert "compact" in combined.lower()

    def test_does_not_exceed_max(self):
        from lidco.core.suggestions import suggest, MAX_SUGGESTIONS, COMPACT_SUGGEST_THRESHOLD
        hints = suggest([], history_len=COMPACT_SUGGEST_THRESHOLD + 10)
        assert len(hints) <= MAX_SUGGESTIONS

    def test_zero_history_no_compact(self):
        from lidco.core.suggestions import suggest
        hints = suggest([], history_len=0)
        combined = " ".join(hints)
        assert "compact" not in combined.lower()
