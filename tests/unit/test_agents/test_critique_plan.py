"""Tests for _critique_plan_node in GraphOrchestrator."""

from __future__ import annotations

import asyncio
from dataclasses import replace as dc_replace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.agents.base import AgentResponse, TokenUsage
from lidco.agents.graph import GraphOrchestrator
from lidco.agents.registry import AgentRegistry
from lidco.llm.base import LLMResponse


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_plan_response(content: str) -> AgentResponse:
    return AgentResponse(
        content=content,
        tool_calls_made=[],
        iterations=3,
        model_used="test-model",
        token_usage=TokenUsage(total_tokens=100, total_cost_usd=0.01),
    )


def _make_orch(critique_response: str | None = "Risk 1. Risk 2. Risk 3.") -> GraphOrchestrator:
    llm = MagicMock()
    if critique_response is not None:
        llm.complete = AsyncMock(return_value=LLMResponse(
            content=critique_response,
            model="cheap",
            tool_calls=[],
            usage={"total_tokens": 50},
            finish_reason="stop",
            cost_usd=0.001,
        ))
    reg = AgentRegistry()
    orch = GraphOrchestrator(llm=llm, agent_registry=reg, agent_timeout=0)
    return orch


def _base_state(plan_content: str) -> dict:
    return {
        "user_message": "add feature X",
        "context": "",
        "selected_agent": "coder",
        "plan_response": _make_plan_response(plan_content),
        "accumulated_tokens": 200,
        "accumulated_cost_usd": 0.02,
    }


# ── enabled path ──────────────────────────────────────────────────────────────


class TestCritiquePlanEnabled:
    def test_critique_appended_to_plan_content(self):
        orch = _make_orch("Risk 1. Missing edge case.")
        state = _base_state("## Implementation Plan\n1. Do something\n2. Do more")
        result = asyncio.run(orch._critique_plan_node(state))

        assert "## Plan Review (auto-generated)" in result["plan_response"].content
        assert "Risk 1. Missing edge case." in result["plan_response"].content

    def test_original_plan_content_preserved(self):
        plan = "## Implementation Plan\n1. Step one\n2. Step two"
        orch = _make_orch("Gap identified.")
        state = _base_state(plan)
        result = asyncio.run(orch._critique_plan_node(state))

        assert plan in result["plan_response"].content

    def test_plan_critique_field_set(self):
        orch = _make_orch("Identified 3 risks.")
        state = _base_state("## Plan\n1. Step")
        result = asyncio.run(orch._critique_plan_node(state))

        assert result.get("plan_critique") == "Identified 3 risks."

    def test_accumulated_tokens_incremented(self):
        orch = _make_orch("critique")
        state = _base_state("## Plan\n1. Step")
        result = asyncio.run(orch._critique_plan_node(state))

        # LLM response has 50 tokens, state starts at 200
        assert result["accumulated_tokens"] == 250

    def test_accumulated_cost_incremented(self):
        orch = _make_orch("critique")
        state = _base_state("## Plan\n1. Step")
        result = asyncio.run(orch._critique_plan_node(state))

        # 0.02 + 0.001
        assert abs(result["accumulated_cost_usd"] - 0.021) < 1e-9

    def test_other_response_fields_preserved(self):
        """plan_response non-content fields (iterations, model, etc.) must survive."""
        plan = "## Plan\n1. A\n2. B"
        orch = _make_orch("One risk.")
        state = _base_state(plan)
        result = asyncio.run(orch._critique_plan_node(state))

        resp = result["plan_response"]
        assert resp.iterations == 3
        assert resp.model_used == "test-model"
        assert resp.token_usage.total_tokens == 100

    def test_separator_line_between_plan_and_critique(self):
        orch = _make_orch("Gap found.")
        state = _base_state("## Plan\n1. Step")
        result = asyncio.run(orch._critique_plan_node(state))
        assert "\n\n---\n" in result["plan_response"].content


# ── disabled path ─────────────────────────────────────────────────────────────


class TestCritiquePlanDisabled:
    def test_state_unchanged_when_disabled(self):
        orch = _make_orch("should not appear")
        orch.set_plan_critique(False)
        state = _base_state("## Plan\n1. Step")
        result = asyncio.run(orch._critique_plan_node(state))

        assert result is state  # exact same object returned

    def test_llm_not_called_when_disabled(self):
        orch = _make_orch()
        orch.set_plan_critique(False)
        state = _base_state("## Plan")
        asyncio.run(orch._critique_plan_node(state))

        orch._llm.complete.assert_not_called()

    def test_plan_critique_field_absent_when_disabled(self):
        orch = _make_orch()
        orch.set_plan_critique(False)
        state = _base_state("## Plan")
        result = asyncio.run(orch._critique_plan_node(state))

        assert "plan_critique" not in result or result.get("plan_critique") is None


# ── no plan_response ──────────────────────────────────────────────────────────


class TestCritiquePlanNoPlan:
    def test_pass_through_when_no_plan_response(self):
        orch = _make_orch()
        state = {
            "user_message": "go",
            "context": "",
            "plan_response": None,
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._critique_plan_node(state))
        assert result is state

    def test_pass_through_when_empty_plan_content(self):
        orch = _make_orch()
        state = _base_state("")  # empty plan content
        result = asyncio.run(orch._critique_plan_node(state))
        # State should pass through unchanged (no critique attempted)
        assert result is state or result.get("plan_critique") is None


# ── failure-safe ──────────────────────────────────────────────────────────────


class TestCritiquePlanFailureSafe:
    def test_exception_in_llm_call_passes_through(self):
        orch = _make_orch()
        orch._llm.complete = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        state = _base_state("## Plan\n1. Step")
        # Must not raise
        result = asyncio.run(orch._critique_plan_node(state))
        # Plan content unchanged
        assert result["plan_response"].content == "## Plan\n1. Step"

    def test_timeout_passes_through(self):
        async def _slow(*args, **kwargs):
            await asyncio.sleep(60)
            return LLMResponse(content="x", model="m", tool_calls=[], usage={}, finish_reason="stop")

        orch = _make_orch()
        orch._llm.complete = _slow
        state = _base_state("## Plan\n1. Step")
        # The node has a 30s internal timeout; we don't want to actually wait
        # so we mock asyncio.wait_for to raise TimeoutError immediately
        with patch("lidco.agents.graph.asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            result = asyncio.run(orch._critique_plan_node(state))

        assert result["plan_response"].content == "## Plan\n1. Step"

    def test_empty_critique_response_passes_through(self):
        """If LLM returns empty string, plan flows through unchanged."""
        orch = _make_orch("")  # empty critique content
        state = _base_state("## Plan\n1. Step")
        result = asyncio.run(orch._critique_plan_node(state))
        assert result["plan_response"].content == "## Plan\n1. Step"
        assert result.get("plan_critique") is None


# ── set_plan_critique setter ──────────────────────────────────────────────────


class TestSetPlanCritique:
    def test_default_is_true(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        assert orch._plan_critique_enabled is True

    def test_set_false(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        orch.set_plan_critique(False)
        assert orch._plan_critique_enabled is False

    def test_set_true_after_false(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        orch.set_plan_critique(False)
        orch.set_plan_critique(True)
        assert orch._plan_critique_enabled is True
