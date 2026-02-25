"""Tests for _revise_plan_node in GraphOrchestrator."""

from __future__ import annotations

import asyncio
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


def _make_llm_response(content: str, tokens: int = 80) -> LLMResponse:
    return LLMResponse(
        content=content,
        model="planner-model",
        tool_calls=[],
        usage={"total_tokens": tokens},
        finish_reason="stop",
        cost_usd=0.005,
    )


def _make_orch(revision_response: str | None = "## Implementation Plan\n### Revised") -> GraphOrchestrator:
    llm = MagicMock()
    if revision_response is not None:
        llm.complete = AsyncMock(return_value=_make_llm_response(revision_response))
    reg = AgentRegistry()
    return GraphOrchestrator(llm=llm, agent_registry=reg, agent_timeout=0)


def _base_state(
    plan_content: str = "## Implementation Plan\n1. Step A\n2. Step B",
    plan_critique: str | None = "**[Missing edge cases]** `foo.py:bar()` — no error handling.",
    accumulated_tokens: int = 200,
    accumulated_cost_usd: float = 0.02,
) -> dict:
    return {
        "user_message": "implement feature X",
        "context": "",
        "selected_agent": "coder",
        "plan_response": _make_plan_response(plan_content),
        "plan_critique": plan_critique,
        "accumulated_tokens": accumulated_tokens,
        "accumulated_cost_usd": accumulated_cost_usd,
    }


# ── applies critique path ─────────────────────────────────────────────────────


class TestRevisePlanAppliesCritique:
    def test_plan_content_replaced_with_revision(self):
        revised = "## Implementation Plan\n### Revised\n1. Step A with error handling."
        orch = _make_orch(revised)
        state = _base_state()
        result = asyncio.run(orch._revise_plan_node(state))

        assert result["plan_response"].content == revised

    def test_plan_revision_field_set(self):
        revised = "## Implementation Plan\n### Revised"
        orch = _make_orch(revised)
        state = _base_state()
        result = asyncio.run(orch._revise_plan_node(state))

        assert result.get("plan_revision") == revised

    def test_plan_critique_cleared_after_revision(self):
        orch = _make_orch("## Plan revised")
        state = _base_state()
        result = asyncio.run(orch._revise_plan_node(state))

        assert result.get("plan_critique") is None

    def test_original_fields_preserved(self):
        """Non-content plan_response fields must survive dc_replace."""
        revised = "## Implementation Plan\n### Addressed"
        orch = _make_orch(revised)
        state = _base_state()
        result = asyncio.run(orch._revise_plan_node(state))

        resp = result["plan_response"]
        assert resp.iterations == 3
        assert resp.model_used == "test-model"
        assert resp.token_usage.total_tokens == 100

    def test_critique_marker_stripped_before_sending(self):
        """Original plan content (without critique section) is passed to LLM."""
        orch = _make_orch("## Plan revised")
        # Plan content with appended critique section
        plan_with_critique = (
            "## Implementation Plan\n1. Step A\n\n---\n"
            "## Plan Review (auto-generated)\nRisk 1."
        )
        state = _base_state(plan_content=plan_with_critique)
        asyncio.run(orch._revise_plan_node(state))

        call_args = orch._llm.complete.call_args
        messages = call_args[0][0]  # first positional arg
        user_msg = next(m for m in messages if m.role == "user")
        # Must contain the original plan
        assert "## Implementation Plan\n1. Step A" in user_msg.content
        # Must NOT include the critique marker in the "Original Plan" section
        assert "## Plan Review (auto-generated)" not in user_msg.content.split("## Critique")[0]

    def test_user_message_included_in_revision_input(self):
        orch = _make_orch("## Plan revised")
        state = _base_state()
        asyncio.run(orch._revise_plan_node(state))

        call_args = orch._llm.complete.call_args
        messages = call_args[0][0]
        user_msg = next(m for m in messages if m.role == "user")
        assert "implement feature X" in user_msg.content

    def test_critique_included_in_revision_input(self):
        critique = "**[Breaking changes]** `core.py:process()` — callers not listed."
        orch = _make_orch("## Plan revised")
        state = _base_state(plan_critique=critique)
        asyncio.run(orch._revise_plan_node(state))

        call_args = orch._llm.complete.call_args
        messages = call_args[0][0]
        user_msg = next(m for m in messages if m.role == "user")
        assert critique in user_msg.content


# ── accumulates tokens ────────────────────────────────────────────────────────


class TestRevisePlanTokens:
    def test_accumulated_tokens_incremented(self):
        orch = _make_orch("## Plan revised")
        state = _base_state(accumulated_tokens=200)
        result = asyncio.run(orch._revise_plan_node(state))

        # LLM response has 80 tokens, state starts at 200
        assert result["accumulated_tokens"] == 280

    def test_accumulated_cost_incremented(self):
        orch = _make_orch("## Plan revised")
        state = _base_state(accumulated_cost_usd=0.02)
        result = asyncio.run(orch._revise_plan_node(state))

        # 0.02 + 0.005
        assert abs(result["accumulated_cost_usd"] - 0.025) < 1e-9


# ── disabled path ─────────────────────────────────────────────────────────────


class TestRevisePlanDisabled:
    def test_state_unchanged_when_disabled(self):
        orch = _make_orch("## Plan revised")
        orch.set_plan_revise(False)
        state = _base_state()
        result = asyncio.run(orch._revise_plan_node(state))

        assert result is state  # exact same object returned

    def test_llm_not_called_when_disabled(self):
        orch = _make_orch()
        orch.set_plan_revise(False)
        state = _base_state()
        asyncio.run(orch._revise_plan_node(state))

        orch._llm.complete.assert_not_called()


# ── no critique path ──────────────────────────────────────────────────────────


class TestRevisePlanNoCritique:
    def test_pass_through_when_critique_is_none(self):
        orch = _make_orch("## Plan revised")
        state = _base_state(plan_critique=None)
        result = asyncio.run(orch._revise_plan_node(state))

        assert result is state

    def test_pass_through_when_critique_is_empty_string(self):
        orch = _make_orch("## Plan revised")
        state = _base_state(plan_critique="")
        result = asyncio.run(orch._revise_plan_node(state))

        assert result is state

    def test_llm_not_called_when_no_critique(self):
        orch = _make_orch()
        state = _base_state(plan_critique=None)
        asyncio.run(orch._revise_plan_node(state))

        orch._llm.complete.assert_not_called()

    def test_pass_through_when_no_plan_response(self):
        orch = _make_orch()
        state = {
            "user_message": "go",
            "context": "",
            "plan_response": None,
            "plan_critique": "Some critique",
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._revise_plan_node(state))
        assert result is state


# ── failure-safe path ─────────────────────────────────────────────────────────


class TestRevisePlanFailureSafe:
    def test_exception_in_llm_call_passes_through(self):
        orch = _make_orch()
        orch._llm.complete = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        state = _base_state()
        original_content = state["plan_response"].content

        result = asyncio.run(orch._revise_plan_node(state))

        # Must not raise; plan content unchanged
        assert result["plan_response"].content == original_content

    def test_timeout_passes_through(self):
        orch = _make_orch()
        state = _base_state()
        original_content = state["plan_response"].content

        with patch("lidco.agents.graph.asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            result = asyncio.run(orch._revise_plan_node(state))

        assert result["plan_response"].content == original_content

    def test_empty_llm_response_passes_through(self):
        orch = _make_orch("")  # empty revision content
        state = _base_state()
        original_content = state["plan_response"].content

        result = asyncio.run(orch._revise_plan_node(state))

        # Empty response → pass through unchanged
        assert result["plan_response"].content == original_content
        assert result.get("plan_revision") is None


# ── set_plan_revise setter ────────────────────────────────────────────────────


class TestSetPlanRevise:
    def test_default_is_true(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        assert orch._plan_revise_enabled is True

    def test_set_false(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        orch.set_plan_revise(False)
        assert orch._plan_revise_enabled is False

    def test_set_true_after_false(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        orch.set_plan_revise(False)
        orch.set_plan_revise(True)
        assert orch._plan_revise_enabled is True

    def test_method_exists(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        assert hasattr(orch, "set_plan_revise")
        assert callable(orch.set_plan_revise)

    def test_revise_plan_node_method_exists(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        assert hasattr(orch, "_revise_plan_node")
        assert callable(orch._revise_plan_node)
