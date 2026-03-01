"""Tests for _parse_execution_map() and execution-map integration in _approve_plan_node."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from lidco.agents.base import AgentResponse, TokenUsage
from lidco.agents.graph import GraphOrchestrator
from lidco.agents.registry import AgentRegistry
from unittest.mock import MagicMock


# ── shared fixtures ────────────────────────────────────────────────────────────

_PLAN_WITH_MAP = """
**Steps:**
1. [Easy | Files: a.py] Do A
2. [Easy | Files: b.py] Do B  [PARALLEL]
3. [Medium | Files: c.py] Wire A+B
4. [Easy | Files: d.py] Do D  [PARALLEL]
5. [Hard | Files: e.py] Finalize

**Execution Map:**
- Critical path: 1 → 3 → 5
- Parallel group A: [2, 4] (run after step 1)
- Integration point: step 3 (wires outputs of 1 and 2)
"""

_PLAN_NO_MAP = """
**Steps:**
1. [Easy | Files: a.py] Do A
2. [Easy | Files: b.py] Do B
3. [Medium | Files: c.py] Wrap up
"""

_PLAN_TWO_GROUPS = """
**Steps:**
1. Setup
2. Task X
3. Task Y
4. Finalize
5. Deploy
6. Monitor
7. Alert

**Execution Map:**
- Critical path: 1 → 4 → 5
- Parallel group A: [2, 4] (run after step 1)
- Parallel group B: [6, 7] (run after step 5)
- Integration point: step 4 (wires 2 and 3)
- Integration point: step 5 (wires 4 and 6)
"""

_PLAN_CRITICAL_ONLY = """
**Steps:**
1. Alpha
2. Beta

**Execution Map:**
- Critical path: 1 → 2
"""


def _make_plan_response(content: str) -> AgentResponse:
    return AgentResponse(
        content=content,
        tool_calls_made=[],
        iterations=2,
        model_used="test-model",
        token_usage=TokenUsage(total_tokens=50, total_cost_usd=0.001),
    )


def _make_orch() -> GraphOrchestrator:
    llm = MagicMock()
    reg = AgentRegistry()
    return GraphOrchestrator(llm=llm, agent_registry=reg, agent_timeout=0)


def _base_state(plan_content: str = _PLAN_WITH_MAP) -> dict:
    return {
        "user_message": "implement feature",
        "context": "",
        "plan_response": _make_plan_response(plan_content),
        "accumulated_tokens": 0,
        "accumulated_cost_usd": 0.0,
    }


# ── TestParseExecutionMap ──────────────────────────────────────────────────────


class TestParseExecutionMap:
    def test_critical_path_parsed(self):
        result = GraphOrchestrator._parse_execution_map(_PLAN_WITH_MAP)
        assert result["critical_path"] == [1, 3, 5]

    def test_parallel_group_parsed(self):
        result = GraphOrchestrator._parse_execution_map(_PLAN_WITH_MAP)
        assert result["parallel_groups"] == [[2, 4]]

    def test_integration_point_parsed(self):
        result = GraphOrchestrator._parse_execution_map(_PLAN_WITH_MAP)
        assert result["integration_points"] == [3]

    def test_no_map_returns_empty_defaults(self):
        result = GraphOrchestrator._parse_execution_map(_PLAN_NO_MAP)
        assert result == {"critical_path": [], "parallel_groups": [], "integration_points": []}

    def test_multiple_parallel_groups(self):
        result = GraphOrchestrator._parse_execution_map(_PLAN_TWO_GROUPS)
        assert result["parallel_groups"] == [[2, 4], [6, 7]]

    def test_multiple_integration_points(self):
        result = GraphOrchestrator._parse_execution_map(_PLAN_TWO_GROUPS)
        assert result["integration_points"] == [4, 5]

    def test_partial_map_critical_path_only(self):
        result = GraphOrchestrator._parse_execution_map(_PLAN_CRITICAL_ONLY)
        assert result["critical_path"] == [1, 2]
        assert result["parallel_groups"] == []
        assert result["integration_points"] == []

    def test_empty_string_returns_defaults(self):
        result = GraphOrchestrator._parse_execution_map("")
        assert result == {"critical_path": [], "parallel_groups": [], "integration_points": []}

    def test_stops_at_next_bold_header(self):
        plan = """
**Execution Map:**
- Critical path: 1 → 2
**Next Section:**
- Critical path: 9 → 10
"""
        result = GraphOrchestrator._parse_execution_map(plan)
        assert result["critical_path"] == [1, 2]

    def test_stops_at_double_hash_section(self):
        plan = """
**Execution Map:**
- Critical path: 3 → 4

## Risk Assessment
- Critical path: 99 → 100
"""
        result = GraphOrchestrator._parse_execution_map(plan)
        assert result["critical_path"] == [3, 4]


# ── TestApproveNodeStoresExecutionMap ─────────────────────────────────────────


class TestApproveNodeStoresExecutionMap:
    def test_execution_map_stored_in_state_on_auto_approve(self):
        """No handler → execution_map is a dict in returned state."""
        orch = _make_orch()
        with patch.object(orch, "_save_approved_plan"):
            result = asyncio.run(orch._approve_plan_node(_base_state()))
        assert isinstance(result.get("execution_map"), dict)
        assert "critical_path" in result["execution_map"]

    def test_execution_map_parallel_groups_augment_parallel_steps(self):
        """Execution map group [2, 4] adds steps 2 and 4 to parallel_steps."""
        # Plan has [PARALLEL] only on step 2; step 4 is added via execution map
        plan = (
            "**Steps:**\n"
            "1. Do A\n"
            "2. Do B  [PARALLEL]\n"
            "3. Wire up\n"
            "4. Do D\n"
            "5. Finalize\n"
            "\n"
            "**Execution Map:**\n"
            "- Critical path: 1 → 3 → 5\n"
            "- Parallel group A: [2, 4] (run after step 1)\n"
        )
        orch = _make_orch()
        with patch.object(orch, "_save_approved_plan"):
            result = asyncio.run(orch._approve_plan_node(_base_state(plan)))
        steps = result["parallel_steps"]
        # Step 4 text should appear (added from execution map)
        assert any("Do D" in s for s in steps), f"parallel_steps={steps}"

    def test_execution_map_deduplicates_with_marker_steps(self):
        """Step already in parallel_steps via [PARALLEL] marker is not duplicated."""
        # Both step 2 and 4 have [PARALLEL] marker; execution map also lists them
        plan = (
            "**Steps:**\n"
            "1. Do A\n"
            "2. Do B  [PARALLEL]\n"
            "3. Wire up\n"
            "4. Do D  [PARALLEL]\n"
            "5. Finalize\n"
            "\n"
            "**Execution Map:**\n"
            "- Critical path: 1 → 3 → 5\n"
            "- Parallel group A: [2, 4]\n"
        )
        orch = _make_orch()
        with patch.object(orch, "_save_approved_plan"):
            result = asyncio.run(orch._approve_plan_node(_base_state(plan)))
        steps = result["parallel_steps"]
        # No duplicates
        assert len(steps) == len(set(steps))
        # Both step 2 and 4 appear exactly once
        b_count = sum(1 for s in steps if "Do B" in s)
        d_count = sum(1 for s in steps if "Do D" in s)
        assert b_count == 1
        assert d_count == 1

    def test_rejection_sets_execution_map_none(self):
        """Handler returning 'Reject' → execution_map is None."""
        orch = _make_orch()
        orch._clarification_handler = lambda prompt, choices, content: "Reject"
        result = asyncio.run(orch._approve_plan_node(_base_state()))
        assert result["plan_approved"] is False
        assert result.get("execution_map") is None

    def test_no_execution_map_section_stores_empty_defaults(self):
        """Plan without Execution Map section → execution_map with empty lists."""
        orch = _make_orch()
        with patch.object(orch, "_save_approved_plan"):
            result = asyncio.run(orch._approve_plan_node(_base_state(_PLAN_NO_MAP)))
        em = result.get("execution_map")
        assert em is not None
        assert em == {"critical_path": [], "parallel_groups": [], "integration_points": []}

    def test_editor_approve_stores_execution_map(self):
        """Plan editor returning filtered plan → execution_map stored from filtered plan."""
        plan = (
            "**Steps:**\n"
            "1. Alpha\n"
            "2. Beta\n"
            "\n"
            "**Execution Map:**\n"
            "- Critical path: 1 → 2\n"
            "- Parallel group A: [1, 2]\n"
        )
        orch = _make_orch()
        orch.set_plan_editor(lambda text: text)  # pass-through editor
        with patch.object(orch, "_save_approved_plan"):
            result = asyncio.run(orch._approve_plan_node(_base_state(plan)))
        assert result["plan_approved"] is True
        assert result["execution_map"]["critical_path"] == [1, 2]

    def test_editor_error_stores_execution_map(self):
        """Editor exception auto-approve path still stores execution_map."""
        orch = _make_orch()
        orch.set_plan_editor(lambda text: (_ for _ in ()).throw(RuntimeError("boom")))
        result = asyncio.run(orch._approve_plan_node(_base_state()))
        assert result["plan_approved"] is True
        assert isinstance(result.get("execution_map"), dict)

    def test_handler_exception_stores_execution_map(self):
        """Clarification handler exception auto-approve path stores execution_map."""
        orch = _make_orch()

        def failing_handler(prompt, choices, content):
            raise RuntimeError("crash")

        orch._clarification_handler = failing_handler
        with patch.object(orch, "_save_approved_plan"):
            result = asyncio.run(orch._approve_plan_node(_base_state()))
        assert result["plan_approved"] is True
        assert isinstance(result.get("execution_map"), dict)
