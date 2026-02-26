"""Tests for Q16 multi-round critique/revise: _re_critique_plan_node + routing."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.agents.base import AgentResponse, TokenUsage
from lidco.agents.graph import GraphOrchestrator
from lidco.agents.registry import AgentRegistry
from lidco.llm.base import LLMResponse


# ── helpers ───────────────────────────────────────────────────────────────────


def _llm_response(content: str, tokens: int = 30) -> LLMResponse:
    return LLMResponse(
        content=content,
        model="cheap",
        tool_calls=[],
        usage={"total_tokens": tokens},
        finish_reason="stop",
        cost_usd=0.001,
    )


def _plan_response(content: str = "## Implementation Plan\n1. Step A") -> AgentResponse:
    return AgentResponse(
        content=content,
        tool_calls_made=[],
        iterations=2,
        model_used="planner",
        token_usage=TokenUsage(total_tokens=200, total_cost_usd=0.02),
    )


def _make_orch(critique_content: str = "**[Missing]** `foo.py` — issue.") -> GraphOrchestrator:
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=_llm_response(critique_content))
    reg = AgentRegistry()
    return GraphOrchestrator(llm=llm, agent_registry=reg, agent_timeout=0)


def _base_state(
    plan_revision_round: int = 0,
    plan_critique: str | None = None,
) -> dict:
    return {
        "user_message": "add feature X",
        "context": "",
        "selected_agent": "coder",
        "plan_response": _plan_response(),
        "plan_critique": plan_critique,
        "plan_revision_round": plan_revision_round,
        "accumulated_tokens": 100,
        "accumulated_cost_usd": 0.01,
    }


# ── _re_critique_plan_node: basic behavior ───────────────────────────────────


class TestReCritiquePlanNode:
    def test_sets_plan_critique_from_llm(self):
        orch = _make_orch("**[Missing edge cases]** issue here.")
        state = _base_state()
        result = asyncio.run(orch._re_critique_plan_node(state))
        assert result.get("plan_critique") == "**[Missing edge cases]** issue here."

    def test_increments_revision_round(self):
        orch = _make_orch("Some critique.")
        state = _base_state(plan_revision_round=0)
        result = asyncio.run(orch._re_critique_plan_node(state))
        assert result["plan_revision_round"] == 1

    def test_increments_round_correctly_from_nonzero(self):
        orch = _make_orch("More critique.")
        state = _base_state(plan_revision_round=1)
        result = asyncio.run(orch._re_critique_plan_node(state))
        assert result["plan_revision_round"] == 2

    def test_accumulates_tokens(self):
        orch = _make_orch("critique")
        state = _base_state()
        state["accumulated_tokens"] = 100
        result = asyncio.run(orch._re_critique_plan_node(state))
        assert result["accumulated_tokens"] == 130  # 100 + 30

    def test_accumulates_cost(self):
        orch = _make_orch("critique")
        state = _base_state()
        state["accumulated_cost_usd"] = 0.01
        result = asyncio.run(orch._re_critique_plan_node(state))
        assert abs(result["accumulated_cost_usd"] - 0.011) < 1e-9

    def test_passthrough_when_no_plan_response(self):
        orch = _make_orch("critique")
        state = _base_state()
        state["plan_response"] = None
        result = asyncio.run(orch._re_critique_plan_node(state))
        assert result is state

    def test_passthrough_on_llm_exception(self):
        orch = _make_orch()
        orch._llm.complete = AsyncMock(side_effect=RuntimeError("LLM down"))
        state = _base_state()
        result = asyncio.run(orch._re_critique_plan_node(state))
        # Should not raise; plan_critique is None or cleared, round incremented
        assert isinstance(result, dict)

    def test_empty_critique_sets_none(self):
        orch = _make_orch("")
        state = _base_state()
        result = asyncio.run(orch._re_critique_plan_node(state))
        assert result.get("plan_critique") is None


# ── _should_revise_again ─────────────────────────────────────────────────────


class TestShouldReviseAgain:
    def test_returns_revise_when_critique_and_round_below_max(self):
        orch = _make_orch()
        orch.set_plan_max_revisions(2)
        state = _base_state(plan_revision_round=0, plan_critique="issue found")
        assert orch._should_revise_again(state) == "revise"

    def test_returns_done_when_round_reaches_max(self):
        orch = _make_orch()
        orch.set_plan_max_revisions(1)
        state = _base_state(plan_revision_round=1, plan_critique="issue found")
        assert orch._should_revise_again(state) == "done"

    def test_returns_done_when_no_critique(self):
        orch = _make_orch()
        orch.set_plan_max_revisions(2)
        state = _base_state(plan_revision_round=0, plan_critique=None)
        assert orch._should_revise_again(state) == "done"

    def test_returns_done_when_critique_is_empty_string(self):
        orch = _make_orch()
        orch.set_plan_max_revisions(2)
        state = _base_state(plan_revision_round=0, plan_critique="")
        assert orch._should_revise_again(state) == "done"

    def test_returns_done_when_max_revisions_is_zero(self):
        orch = _make_orch()
        orch.set_plan_max_revisions(0)
        state = _base_state(plan_revision_round=0, plan_critique="issues here")
        assert orch._should_revise_again(state) == "done"

    def test_revise_when_round_is_zero_max_is_one(self):
        orch = _make_orch()
        orch.set_plan_max_revisions(1)
        state = _base_state(plan_revision_round=0, plan_critique="issues found")
        assert orch._should_revise_again(state) == "revise"


# ── set_plan_max_revisions ────────────────────────────────────────────────────


class TestSetPlanMaxRevisions:
    def test_default_is_one(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        assert orch._plan_max_revisions == 1

    def test_set_to_zero(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        orch.set_plan_max_revisions(0)
        assert orch._plan_max_revisions == 0

    def test_negative_clamped_to_zero(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        orch.set_plan_max_revisions(-5)
        assert orch._plan_max_revisions == 0

    def test_set_to_three(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        orch.set_plan_max_revisions(3)
        assert orch._plan_max_revisions == 3

    def test_method_exists(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        assert hasattr(orch, "set_plan_max_revisions")
        assert callable(orch.set_plan_max_revisions)

    def test_re_critique_node_method_exists(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        assert hasattr(orch, "_re_critique_plan_node")
        assert callable(orch._re_critique_plan_node)

    def test_should_revise_again_method_exists(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        assert hasattr(orch, "_should_revise_again")
        assert callable(orch._should_revise_again)
