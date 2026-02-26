"""Tests for Q16 plan memory: _find_similar_plan + _save_approved_plan."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.agents.base import AgentResponse, TokenUsage
from lidco.agents.graph import GraphOrchestrator
from lidco.agents.registry import AgentRegistry
from lidco.core.memory import MemoryEntry, MemoryStore


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_orch(with_memory: bool = True) -> tuple[GraphOrchestrator, MagicMock | None]:
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=MagicMock(
        content="plan", model="m", tool_calls=[],
        usage={"total_tokens": 10}, finish_reason="stop", cost_usd=0.0,
    ))
    reg = AgentRegistry()
    orch = GraphOrchestrator(llm=llm, agent_registry=reg, agent_timeout=0)
    if with_memory:
        memory = MagicMock(spec=MemoryStore)
        orch.set_memory_store(memory)
        orch.set_plan_memory(True)
        return orch, memory
    orch.set_plan_memory(True)
    return orch, None


def _make_entry(key: str, content: str) -> MemoryEntry:
    return MemoryEntry(
        key=key,
        content=content,
        category="approved_plans",
        tags=("auto-plan",),
        created_at="",
        source="",
    )


# ── _find_similar_plan ────────────────────────────────────────────────────────


class TestFindSimilarPlan:
    def test_returns_none_when_no_memory(self):
        orch, _ = _make_orch(with_memory=False)
        result = orch._find_similar_plan("add feature")
        assert result is None

    def test_returns_none_when_no_matching_plans(self):
        orch, memory = _make_orch()
        memory.list_all.return_value = []
        result = orch._find_similar_plan("add authentication")
        assert result is None

    def test_returns_similar_plan_when_found(self):
        orch, memory = _make_orch()
        entry = _make_entry(
            "plan_abc123",
            "Task: add authentication\n\n## Implementation Plan\n1. Step A"
        )
        memory.list_all.return_value = [entry]
        result = orch._find_similar_plan("add authentication to the app")
        assert result is not None
        assert "Similar Past Plan" in result

    def test_returns_none_when_no_keyword_overlap(self):
        orch, memory = _make_orch()
        entry = _make_entry(
            "plan_xyz",
            "Task: database migration\n\n## Implementation Plan\n1. Step A"
        )
        memory.list_all.return_value = [entry]
        result = orch._find_similar_plan("add authentication tokens")
        assert result is None

    def test_plan_key_in_result(self):
        orch, memory = _make_orch()
        entry = _make_entry("plan_abc123", "Task: refactor auth\n\n1. refactor auth step")
        memory.list_all.return_value = [entry]
        result = orch._find_similar_plan("refactor auth module")
        assert result is not None
        assert "plan_abc123" in result

    def test_picks_best_matching_plan(self):
        orch, memory = _make_orch()
        low_match = _make_entry("plan_low", "Task: auth step\n\nsome plan")
        high_match = _make_entry("plan_high", "Task: add auth tokens login\n\nadd auth tokens login plan")
        memory.list_all.return_value = [low_match, high_match]
        result = orch._find_similar_plan("add auth tokens login")
        assert result is not None
        assert "plan_high" in result

    def test_handles_memory_exception_gracefully(self):
        orch, memory = _make_orch()
        memory.list_all.side_effect = RuntimeError("disk error")
        result = orch._find_similar_plan("add feature")
        assert result is None

    def test_truncates_long_content(self):
        orch, memory = _make_orch()
        long_content = "add feature\n\n" + "x" * 5000
        entry = _make_entry("plan_long", long_content)
        memory.list_all.return_value = [entry]
        result = orch._find_similar_plan("add feature")
        # Should not crash; content is capped at 2000
        assert result is not None
        assert len(result) <= 3000  # header + 2000 chars content


# ── _save_approved_plan ──────────────────────────────────────────────────────


class TestSaveApprovedPlan:
    def test_calls_memory_add(self):
        orch, memory = _make_orch()
        orch._save_approved_plan("add feature X", "## Implementation Plan\n1. Step A")
        memory.add.assert_called_once()

    def test_uses_approved_plans_category(self):
        orch, memory = _make_orch()
        orch._save_approved_plan("task text", "## Plan")
        call_kwargs = memory.add.call_args[1]
        assert call_kwargs.get("category") == "approved_plans"

    def test_strips_critique_section_before_saving(self):
        orch, memory = _make_orch()
        plan_with_critique = (
            "## Implementation Plan\n1. Step A\n\n---\n"
            "## Plan Review (auto-generated)\nRisk 1."
        )
        orch._save_approved_plan("task", plan_with_critique)
        saved_content = memory.add.call_args[1].get("content") or memory.add.call_args[0][1]
        assert "## Plan Review (auto-generated)" not in saved_content

    def test_includes_user_message_in_saved_content(self):
        orch, memory = _make_orch()
        orch._save_approved_plan("implement auth JWT", "## Plan")
        saved_content = memory.add.call_args[1].get("content") or ""
        assert "implement auth JWT" in saved_content

    def test_does_nothing_when_no_memory(self):
        orch, _ = _make_orch(with_memory=False)
        # Should not raise
        orch._save_approved_plan("task", "## Plan")

    def test_does_nothing_when_plan_memory_disabled(self):
        orch, memory = _make_orch()
        orch.set_plan_memory(False)
        orch._save_approved_plan("task", "## Plan")
        memory.add.assert_not_called()

    def test_handles_memory_exception_gracefully(self):
        orch, memory = _make_orch()
        memory.add.side_effect = RuntimeError("write error")
        # Should not raise
        orch._save_approved_plan("task", "## Plan")


# ── set_plan_memory setter ────────────────────────────────────────────────────


class TestSetPlanMemory:
    def test_default_is_true(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        assert orch._plan_memory_enabled is True

    def test_set_false(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        orch.set_plan_memory(False)
        assert orch._plan_memory_enabled is False

    def test_set_true_after_false(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        orch.set_plan_memory(False)
        orch.set_plan_memory(True)
        assert orch._plan_memory_enabled is True
