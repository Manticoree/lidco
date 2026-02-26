"""Tests for Q16 pre-planning snapshot: symbol extraction + git/coverage snapshot."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.agents.graph import GraphOrchestrator
from lidco.agents.registry import AgentRegistry


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_orch(preplan_snapshot: bool = True) -> GraphOrchestrator:
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=MagicMock(
        content="plan",
        model="m",
        tool_calls=[],
        usage={"total_tokens": 10},
        finish_reason="stop",
        cost_usd=0.0,
    ))
    reg = AgentRegistry()
    orch = GraphOrchestrator(llm=llm, agent_registry=reg, agent_timeout=0)
    orch.set_preplan_snapshot(preplan_snapshot)
    return orch


# ── _extract_mentioned_symbols ────────────────────────────────────────────────


class TestExtractMentionedSymbols:
    def test_single_backtick_symbol(self):
        result = GraphOrchestrator._extract_mentioned_symbols("Fix the `foo_bar` function")
        assert "foo_bar" in result

    def test_multiple_symbols(self):
        result = GraphOrchestrator._extract_mentioned_symbols(
            "Refactor `handle()` and update `GraphOrchestrator`"
        )
        assert "handle()" in result
        assert "GraphOrchestrator" in result

    def test_no_backticks_returns_empty(self):
        result = GraphOrchestrator._extract_mentioned_symbols("Fix the function")
        assert result == []

    def test_symbol_with_space_excluded(self):
        result = GraphOrchestrator._extract_mentioned_symbols("`some text with spaces`")
        assert result == []

    def test_long_symbol_excluded(self):
        long_sym = "a" * 61
        result = GraphOrchestrator._extract_mentioned_symbols(f"`{long_sym}`")
        assert result == []

    def test_capped_at_ten(self):
        text = " ".join(f"`sym{i}`" for i in range(15))
        result = GraphOrchestrator._extract_mentioned_symbols(text)
        assert len(result) == 10

    def test_empty_backticks_excluded(self):
        result = GraphOrchestrator._extract_mentioned_symbols("see ``")
        assert result == []

    def test_path_like_symbol(self):
        result = GraphOrchestrator._extract_mentioned_symbols("edit `src/lidco/agents/graph.py`")
        assert "src/lidco/agents/graph.py" in result


# ── _build_preplan_snapshot ───────────────────────────────────────────────────


class TestBuildPreplanSnapshot:
    def test_returns_empty_when_disabled(self):
        orch = _make_orch(preplan_snapshot=False)
        result = asyncio.run(orch._build_preplan_snapshot("add feature"))
        assert result == ""

    def test_returns_section_header_when_git_log_available(self):
        orch = _make_orch()
        with patch.object(orch, "_run_git_log", return_value="abc123 fix thing"):
            with patch("lidco.agents.graph.build_coverage_context", side_effect=Exception("no cov"), create=True):
                result = asyncio.run(orch._build_preplan_snapshot("add feature"))
        assert "Pre-planning Snapshot" in result
        assert "abc123 fix thing" in result

    def test_returns_empty_when_both_sources_empty(self):
        orch = _make_orch()
        with patch.object(orch, "_run_git_log", return_value=""):
            with patch("lidco.core.coverage_reader.build_coverage_context", side_effect=Exception):
                result = asyncio.run(orch._build_preplan_snapshot("add feature"))
        assert result == ""

    def test_failure_safe_on_git_log_exception(self):
        orch = _make_orch()
        with patch.object(orch, "_run_git_log", side_effect=RuntimeError("git failed")):
            # Should not raise
            result = asyncio.run(orch._build_preplan_snapshot("msg"))
        # May return "" if coverage also fails — just verify no exception
        assert isinstance(result, str)

    def test_coverage_section_included(self):
        orch = _make_orch()
        with patch.object(orch, "_run_git_log", return_value=""):
            with patch("lidco.core.coverage_reader.build_coverage_context",
                       return_value="## Coverage\n80%"):
                result = asyncio.run(orch._build_preplan_snapshot("add feature"))
        assert "80%" in result


# ── _build_symbol_context ─────────────────────────────────────────────────────


class TestBuildSymbolContext:
    def test_empty_symbols_returns_empty(self):
        orch = _make_orch()
        result = asyncio.run(orch._build_symbol_context([]))
        assert result == ""

    def test_returns_section_when_grep_finds_matches(self):
        orch = _make_orch()
        with patch.object(orch, "_grep_symbol", return_value="src/foo.py:10:def handle():"):
            result = asyncio.run(orch._build_symbol_context(["handle"]))
        assert "Referenced Symbols" in result
        assert "handle" in result

    def test_returns_empty_when_grep_finds_nothing(self):
        orch = _make_orch()
        with patch.object(orch, "_grep_symbol", return_value=""):
            result = asyncio.run(orch._build_symbol_context(["no_match"]))
        assert result == ""

    def test_timeout_per_symbol_is_handled(self):
        orch = _make_orch()
        with patch.object(orch, "_grep_symbol", side_effect=RuntimeError("err")):
            # Should not raise, just skip the symbol
            result = asyncio.run(orch._build_symbol_context(["bad_sym"]))
        assert isinstance(result, str)


# ── set_preplan_snapshot setter ───────────────────────────────────────────────


class TestSetPreplanSnapshot:
    def test_default_is_true(self):
        orch = _make_orch()
        assert orch._preplan_snapshot_enabled is True

    def test_set_false(self):
        orch = _make_orch()
        orch.set_preplan_snapshot(False)
        assert orch._preplan_snapshot_enabled is False

    def test_set_true_after_false(self):
        orch = _make_orch()
        orch.set_preplan_snapshot(False)
        orch.set_preplan_snapshot(True)
        assert orch._preplan_snapshot_enabled is True
