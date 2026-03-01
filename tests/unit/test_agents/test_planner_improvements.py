"""Tests for Q14 planner improvements: tools, config, graph wiring."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.agents.builtin.planner import PLANNER_SYSTEM_PROMPT, create_planner_agent
from lidco.agents.graph import GraphOrchestrator
from lidco.agents.registry import AgentRegistry
from lidco.core.config import AgentsConfig


# ── Planner agent tools ───────────────────────────────────────────────────────


class TestPlannerTools:
    def _make_planner(self):
        llm = MagicMock()
        registry = MagicMock()
        registry.get.return_value = None
        return create_planner_agent(llm, registry)

    def test_planner_has_seven_tools(self):
        planner = self._make_planner()
        assert len(planner.config.tools) == 7

    def test_planner_has_arch_diagram(self):
        planner = self._make_planner()
        assert "arch_diagram" in planner.config.tools

    def test_planner_has_find_test_gaps(self):
        planner = self._make_planner()
        assert "find_test_gaps" in planner.config.tools

    def test_planner_has_tree(self):
        planner = self._make_planner()
        assert "tree" in planner.config.tools

    def test_planner_keeps_core_tools(self):
        planner = self._make_planner()
        for tool in ("file_read", "glob", "grep", "ask_user"):
            assert tool in planner.config.tools

    def test_planner_name(self):
        planner = self._make_planner()
        assert planner.config.name == "planner"


# ── Planner system prompt content ─────────────────────────────────────────────


class TestPlannerSystemPromptContent:
    def test_has_self_critique_phase(self):
        assert "Self-Critique" in PLANNER_SYSTEM_PROMPT

    def test_mentions_arch_diagram_tool(self):
        assert "arch_diagram" in PLANNER_SYSTEM_PROMPT

    def test_mentions_find_test_gaps_tool(self):
        assert "find_test_gaps" in PLANNER_SYSTEM_PROMPT

    def test_has_risk_assessment_section(self):
        assert "Risk Assessment" in PLANNER_SYSTEM_PROMPT

    def test_has_test_impact_section(self):
        assert "Test Impact" in PLANNER_SYSTEM_PROMPT

    def test_has_callers_dependents_section(self):
        assert "Callers/Dependents" in PLANNER_SYSTEM_PROMPT

    def test_has_reasoning_approach_section(self):
        assert "Reasoning & Approach" in PLANNER_SYSTEM_PROMPT

    def test_has_alternative_considered_section(self):
        assert "Alternative Considered" in PLANNER_SYSTEM_PROMPT

    def test_has_chain_of_thought_in_output_format(self):
        assert "Chain of Thought" in PLANNER_SYSTEM_PROMPT

    def test_chain_of_thought_before_steps(self):
        cot_idx = PLANNER_SYSTEM_PROMPT.index("Chain of Thought")
        steps_idx = PLANNER_SYSTEM_PROMPT.index("**Steps:**")
        assert cot_idx < steps_idx, "Chain of Thought must appear before Steps in output format"

    def test_phase_2_mentions_all_callers(self):
        assert "ALL callers" in PLANNER_SYSTEM_PROMPT

    def test_phase_5_has_eight_points(self):
        # Phase 5 items are numbered 1-8
        assert "7." in PLANNER_SYSTEM_PROMPT
        assert "8." in PLANNER_SYSTEM_PROMPT

    def test_phase_5_reasoning_visible_point(self):
        assert "reasoning visible" in PLANNER_SYSTEM_PROMPT.lower()

    def test_phase_5_risks_ranked_by_severity(self):
        assert "severity" in PLANNER_SYSTEM_PROMPT.lower()

    def test_has_complexity_gate_phase(self):
        assert "Phase 0" in PLANNER_SYSTEM_PROMPT

    def test_has_trivial_label(self):
        assert "TRIVIAL" in PLANNER_SYSTEM_PROMPT

    def test_has_complex_label(self):
        assert "COMPLEX" in PLANNER_SYSTEM_PROMPT

    def test_step_format_has_files_label(self):
        assert "Files:" in PLANNER_SYSTEM_PROMPT

    def test_step_format_has_verify_label(self):
        assert "Verify:" in PLANNER_SYSTEM_PROMPT

    def test_step_format_has_deps_label(self):
        assert "Deps:" in PLANNER_SYSTEM_PROMPT

    def test_has_execution_map_section(self):
        assert "Execution Map" in PLANNER_SYSTEM_PROMPT

    def test_has_integration_point_keyword(self):
        assert "integration" in PLANNER_SYSTEM_PROMPT.lower()

    def test_phase_5_has_nine_or_more_points(self):
        assert "9." in PLANNER_SYSTEM_PROMPT


# ── AgentsConfig.plan_critique ────────────────────────────────────────────────


class TestAgentsConfigPlanCritique:
    def test_default_plan_critique_is_true(self):
        cfg = AgentsConfig()
        assert cfg.plan_critique is True

    def test_plan_critique_can_be_disabled(self):
        cfg = AgentsConfig(plan_critique=False)
        assert cfg.plan_critique is False

    def test_plan_critique_can_be_enabled_explicitly(self):
        cfg = AgentsConfig(plan_critique=True)
        assert cfg.plan_critique is True


# ── Graph edge: execute_planner → critique_plan ───────────────────────────────


class TestGraphCritiquePlanEdge:
    """Verify that _critique_plan_node is wired into the graph path."""

    def _make_orch(self) -> GraphOrchestrator:
        llm = MagicMock()
        llm.complete = AsyncMock(return_value=MagicMock(
            content="Risk A. Risk B.",
            model="cheap",
            tool_calls=[],
            usage={"total_tokens": 20},
            finish_reason="stop",
            cost_usd=0.0,
        ))
        reg = AgentRegistry()
        return GraphOrchestrator(llm=llm, agent_registry=reg, agent_timeout=0)

    def test_critique_node_method_exists(self):
        orch = self._make_orch()
        assert hasattr(orch, "_critique_plan_node")
        assert callable(orch._critique_plan_node)

    def test_set_plan_critique_method_exists(self):
        orch = self._make_orch()
        assert hasattr(orch, "set_plan_critique")
        assert callable(orch.set_plan_critique)

    def test_plan_critique_enabled_by_default(self):
        orch = self._make_orch()
        assert orch._plan_critique_enabled is True

    def test_critique_state_key_processed(self):
        """Critique node returns plan_critique key when LLM provides content."""
        from lidco.agents.base import AgentResponse, TokenUsage

        orch = self._make_orch()
        state = {
            "user_message": "add X",
            "context": "",
            "selected_agent": "coder",
            "plan_response": AgentResponse(
                content="## Plan\n1. Step",
                tool_calls_made=[],
                iterations=1,
                model_used="test-model",
                token_usage=TokenUsage(total_tokens=100, total_cost_usd=0.01),
            ),
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._critique_plan_node(state))
        assert "plan_critique" in result
        assert result["plan_critique"] == "Risk A. Risk B."
