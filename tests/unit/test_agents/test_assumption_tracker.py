"""Tests for Q16 assumption tracker: parse, store, and revise unverified assumptions."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.agents.base import AgentResponse, TokenUsage
from lidco.agents.builtin.planner import PLANNER_SYSTEM_PROMPT
from lidco.agents.graph import GraphOrchestrator, _REVISE_SYSTEM_PROMPT
from lidco.agents.registry import AgentRegistry


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_orch() -> GraphOrchestrator:
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=MagicMock(
        content="revised plan",
        model="m",
        tool_calls=[],
        usage={"total_tokens": 50},
        finish_reason="stop",
        cost_usd=0.001,
    ))
    reg = AgentRegistry()
    return GraphOrchestrator(llm=llm, agent_registry=reg, agent_timeout=0)


PLAN_WITH_ASSUMPTIONS = """\
## Implementation Plan

**Goal:** Refactor auth module.

**Assumptions:**
- Auth uses JWT tokens [✓ Verified — found `jwt.encode` in `auth.py:45`]
- No other module imports `verify_token` directly [⚠ Unverified — only checked top-level imports]

**Chain of Thought:**
1. Found auth.py with JWT usage.
2. Plan is straightforward.

**Steps:**
1. [Easy] `auth.py` — update `verify_token` signature
"""


# ── _parse_plan_assumptions ───────────────────────────────────────────────────


class TestParsePlanAssumptions:
    def test_extracts_assumption_lines(self):
        result = GraphOrchestrator._parse_plan_assumptions(PLAN_WITH_ASSUMPTIONS)
        assert len(result) == 2

    def test_verified_assumption_extracted(self):
        result = GraphOrchestrator._parse_plan_assumptions(PLAN_WITH_ASSUMPTIONS)
        assert any("✓ Verified" in a for a in result)

    def test_unverified_assumption_extracted(self):
        result = GraphOrchestrator._parse_plan_assumptions(PLAN_WITH_ASSUMPTIONS)
        assert any("⚠ Unverified" in a for a in result)

    def test_empty_plan_returns_empty(self):
        result = GraphOrchestrator._parse_plan_assumptions("")
        assert result == []

    def test_plan_without_assumptions_returns_empty(self):
        plan = "## Implementation Plan\n**Steps:**\n1. Do thing"
        result = GraphOrchestrator._parse_plan_assumptions(plan)
        assert result == []

    def test_stops_at_next_bold_header(self):
        plan = (
            "**Assumptions:**\n"
            "- Assumption A\n"
            "- Assumption B\n"
            "**Chain of Thought:**\n"
            "- Should not be included\n"
        )
        result = GraphOrchestrator._parse_plan_assumptions(plan)
        assert len(result) == 2
        assert all("Assumption" in a for a in result)

    def test_stops_at_hash_header(self):
        plan = (
            "**Assumptions:**\n"
            "- Only assumption\n"
            "## Next Section\n"
            "- Not an assumption\n"
        )
        result = GraphOrchestrator._parse_plan_assumptions(plan)
        assert result == ["- Only assumption"]

    def test_skips_blank_lines(self):
        plan = "**Assumptions:**\n\n- Assumption A\n\n- Assumption B\n**Steps:**"
        result = GraphOrchestrator._parse_plan_assumptions(plan)
        assert len(result) == 2


# ── assumptions stored in state after planner runs ───────────────────────────


class TestAssumptionsStoredInState:
    def test_plan_assumptions_key_in_state_after_planner(self):
        """After _execute_planner_node, plan_assumptions is set in state."""
        orch = _make_orch()

        plan_content = PLAN_WITH_ASSUMPTIONS
        mock_agent_response = AgentResponse(
            content=plan_content,
            tool_calls_made=[],
            iterations=1,
            model_used="test",
            token_usage=TokenUsage(total_tokens=100, total_cost_usd=0.01),
        )

        # Patch the planner agent in registry
        planner = MagicMock()
        planner.run = AsyncMock(return_value=mock_agent_response)
        planner.set_status_callback = MagicMock()
        planner.set_permission_handler = MagicMock()
        planner.set_token_callback = MagicMock()
        planner.set_continue_handler = MagicMock()
        planner.set_clarification_handler = MagicMock()
        planner.set_stream_callback = MagicMock()
        planner.set_tool_event_callback = MagicMock()
        orch._registry._agents = {"planner": planner}

        state = {
            "user_message": "refactor auth",
            "context": "",
            "selected_agent": "coder",
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
            "plan_assumptions": [],
            "plan_revision_round": 0,
        }
        result = asyncio.run(orch._execute_planner_node(state))

        assert "plan_assumptions" in result
        assert len(result["plan_assumptions"]) == 2

    def test_no_assumptions_gives_empty_list(self):
        orch = _make_orch()

        plan_content = "## Implementation Plan\n**Steps:**\n1. Do thing"
        mock_agent_response = AgentResponse(
            content=plan_content,
            tool_calls_made=[],
            iterations=1,
            model_used="test",
            token_usage=TokenUsage(total_tokens=50, total_cost_usd=0.005),
        )

        planner = MagicMock()
        planner.run = AsyncMock(return_value=mock_agent_response)
        planner.set_status_callback = MagicMock()
        planner.set_permission_handler = MagicMock()
        planner.set_token_callback = MagicMock()
        planner.set_continue_handler = MagicMock()
        planner.set_clarification_handler = MagicMock()
        planner.set_stream_callback = MagicMock()
        planner.set_tool_event_callback = MagicMock()
        orch._registry._agents = {"planner": planner}

        state = {
            "user_message": "simple task",
            "context": "",
            "selected_agent": "coder",
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
            "plan_assumptions": [],
            "plan_revision_round": 0,
        }
        result = asyncio.run(orch._execute_planner_node(state))
        assert result["plan_assumptions"] == []


# ── PLANNER_SYSTEM_PROMPT has Assumptions section ────────────────────────────


class TestPlannerPromptAssumptions:
    def test_assumptions_section_in_output_format(self):
        assert "**Assumptions:**" in PLANNER_SYSTEM_PROMPT

    def test_verified_marker_in_prompt(self):
        assert "✓ Verified" in PLANNER_SYSTEM_PROMPT

    def test_unverified_marker_in_prompt(self):
        assert "⚠ Unverified" in PLANNER_SYSTEM_PROMPT

    def test_assumptions_before_chain_of_thought(self):
        assumptions_idx = PLANNER_SYSTEM_PROMPT.index("**Assumptions:**")
        cot_idx = PLANNER_SYSTEM_PROMPT.index("**Chain of Thought:**")
        assert assumptions_idx < cot_idx, "Assumptions must appear before Chain of Thought"


# ── _REVISE_SYSTEM_PROMPT challenges unverified assumptions ──────────────────


class TestRevisePromptChallengesAssumptions:
    def test_revise_prompt_mentions_unverified(self):
        assert "Unverified" in _REVISE_SYSTEM_PROMPT

    def test_revise_prompt_mentions_assumptions_section(self):
        assert "Assumptions" in _REVISE_SYSTEM_PROMPT

    def test_revise_prompt_requires_addressing_unverified(self):
        assert "⚠ Unverified" in _REVISE_SYSTEM_PROMPT
