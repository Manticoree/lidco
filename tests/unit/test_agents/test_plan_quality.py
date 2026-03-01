"""Tests for Q17 plan quality improvements:

- _compute_critique_budget  — adaptive token budget by step count
- _check_plan_sections      — missing required section detection
- _compute_plan_health      — 0-100 quality score formula
- Integration: _verify_assumptions_node returns plan_section_issues
- Integration: _approve_plan_node emits health score and stores plan_health_score
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.agents.base import AgentResponse, TokenUsage
from lidco.agents.graph import GraphOrchestrator, _REQUIRED_PLAN_SECTIONS
from lidco.agents.registry import AgentRegistry
from lidco.llm.base import LLMResponse


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_orch() -> GraphOrchestrator:
    llm = MagicMock()
    reg = AgentRegistry()
    return GraphOrchestrator(llm=llm, agent_registry=reg, agent_timeout=0)


def _make_plan_response(content: str) -> AgentResponse:
    return AgentResponse(
        content=content,
        tool_calls_made=[],
        iterations=2,
        model_used="test",
        token_usage=TokenUsage(total_tokens=50, total_cost_usd=0.001),
    )


def _full_plan(n_steps: int = 3, with_verify: bool = True) -> str:
    """Build a minimal but complete plan with all required sections."""
    steps = []
    for i in range(1, n_steps + 1):
        steps.append(f"{i}. [Easy | Files: a.py] Do step {i}")
        if with_verify:
            steps.append(f"   Verify: step {i} done")
        steps.append("   Deps: none")
    return (
        "## Implementation Plan\n\n"
        "**Goal:** Test goal.\n\n"
        "**Assumptions:**\n- Everything is fine [✓ Verified]\n\n"
        "**Steps:**\n" + "\n".join(steps) + "\n\n"
        "**Risk Assessment:**\n"
        "| Risk | Likelihood | Mitigation |\n"
        "|------|-----------|------------|\n"
        "| None | Low | N/A |\n\n"
        "**Test Impact:**\n"
        "- Tests to update: none\n"
        "- New tests needed: none\n"
    )


# ── _compute_critique_budget ──────────────────────────────────────────────────


class TestComputeCritiqueBudget:
    def test_empty_plan_returns_minimum(self):
        result = GraphOrchestrator._compute_critique_budget("")
        assert result <= 300

    def test_one_step_returns_small_budget(self):
        plan = "1. Do the thing"
        result = GraphOrchestrator._compute_critique_budget(plan)
        assert result == 300

    def test_two_steps_returns_small_budget(self):
        plan = "1. First step\n2. Second step"
        result = GraphOrchestrator._compute_critique_budget(plan)
        assert result == 300

    def test_three_steps_returns_medium_budget(self):
        plan = "1. A\n2. B\n3. C"
        result = GraphOrchestrator._compute_critique_budget(plan)
        assert result == 500

    def test_five_steps_returns_medium_budget(self):
        plan = "\n".join(f"{i}. Step {i}" for i in range(1, 6))
        result = GraphOrchestrator._compute_critique_budget(plan)
        assert result == 500

    def test_six_steps_returns_full_budget(self):
        plan = "\n".join(f"{i}. Step {i}" for i in range(1, 7))
        result = GraphOrchestrator._compute_critique_budget(plan)
        assert result == 800

    def test_ten_steps_returns_full_budget(self):
        plan = "\n".join(f"{i}. Step {i}" for i in range(1, 11))
        result = GraphOrchestrator._compute_critique_budget(plan)
        assert result == 800

    def test_returns_int(self):
        assert isinstance(GraphOrchestrator._compute_critique_budget("1. Step"), int)

    def test_never_raises_on_garbage(self):
        try:
            result = GraphOrchestrator._compute_critique_budget("not a plan at all!!!")
            assert isinstance(result, int)
        except Exception as e:
            pytest.fail(f"_compute_critique_budget raised: {e}")

    def test_budget_increases_with_step_count(self):
        short = GraphOrchestrator._compute_critique_budget("1. A\n2. B")
        medium = GraphOrchestrator._compute_critique_budget("\n".join(f"{i}. S" for i in range(1, 5)))
        long_ = GraphOrchestrator._compute_critique_budget("\n".join(f"{i}. S" for i in range(1, 9)))
        assert short <= medium <= long_


# ── critique node uses adaptive budget ────────────────────────────────────────


class TestCritiqueNodeAdaptiveBudget:
    def _make_orch_with_capture(self) -> tuple[GraphOrchestrator, list[int]]:
        captured: list[int] = []
        llm = MagicMock()

        async def fake_complete(messages, *, temperature, max_tokens, role, **kw):
            captured.append(max_tokens)
            return LLMResponse(
                content="No critical gaps identified.",
                model="cheap",
                tool_calls=[],
                usage={"total_tokens": 10},
                finish_reason="stop",
                cost_usd=0.0,
            )

        llm.complete = fake_complete
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg, agent_timeout=0)
        return orch, captured

    def test_short_plan_uses_small_budget(self):
        orch, captured = self._make_orch_with_capture()
        state = {
            "user_message": "fix bug",
            "context": "",
            "plan_response": _make_plan_response("## Plan\n1. Fix it"),
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        asyncio.run(orch._critique_plan_node(state))
        assert captured == [300]

    def test_long_plan_uses_full_budget(self):
        orch, captured = self._make_orch_with_capture()
        big_plan = "## Plan\n" + "\n".join(f"{i}. Step {i}" for i in range(1, 9))
        state = {
            "user_message": "big refactor",
            "context": "",
            "plan_response": _make_plan_response(big_plan),
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        asyncio.run(orch._critique_plan_node(state))
        assert captured == [800]


# ── _check_plan_sections ──────────────────────────────────────────────────────


class TestCheckPlanSections:
    def test_all_sections_present_returns_empty(self):
        plan = _full_plan()
        assert GraphOrchestrator._check_plan_sections(plan) == []

    def test_missing_goal_returned(self):
        plan = (
            "**Assumptions:**\n- ok\n\n"
            "**Steps:**\n1. Go\n\n"
            "**Risk Assessment:**\n| Risk | L | M |\n|---|---|---|\n\n"
            "**Test Impact:**\n- none\n"
        )
        missing = GraphOrchestrator._check_plan_sections(plan)
        assert "Goal" in missing

    def test_missing_steps_returned(self):
        plan = (
            "**Goal:** X\n\n"
            "**Assumptions:**\n- ok\n\n"
            "**Risk Assessment:**\n| R | L | M |\n|---|---|---|\n\n"
            "**Test Impact:**\n- none\n"
        )
        missing = GraphOrchestrator._check_plan_sections(plan)
        assert "Steps" in missing

    def test_missing_risk_assessment_returned(self):
        plan = (
            "**Goal:** X\n\n"
            "**Assumptions:**\n- ok\n\n"
            "**Steps:**\n1. Go\n\n"
            "**Test Impact:**\n- none\n"
        )
        missing = GraphOrchestrator._check_plan_sections(plan)
        assert "Risk Assessment" in missing

    def test_missing_assumptions_returned(self):
        plan = (
            "**Goal:** X\n\n"
            "**Steps:**\n1. Go\n\n"
            "**Risk Assessment:**\n| R | L | M |\n|---|---|---|\n\n"
            "**Test Impact:**\n- none\n"
        )
        missing = GraphOrchestrator._check_plan_sections(plan)
        assert "Assumptions" in missing

    def test_missing_test_impact_returned(self):
        plan = (
            "**Goal:** X\n\n"
            "**Assumptions:**\n- ok\n\n"
            "**Steps:**\n1. Go\n\n"
            "**Risk Assessment:**\n| R | L | M |\n|---|---|---|\n"
        )
        missing = GraphOrchestrator._check_plan_sections(plan)
        assert "Test Impact" in missing

    def test_multiple_missing_sections(self):
        missing = GraphOrchestrator._check_plan_sections("Just some prose, no structure.")
        assert len(missing) == 5  # all 5 required sections absent

    def test_empty_plan_returns_all_missing(self):
        missing = GraphOrchestrator._check_plan_sections("")
        assert len(missing) == 5

    def test_returns_list(self):
        result = GraphOrchestrator._check_plan_sections("")
        assert isinstance(result, list)

    def test_never_raises_on_garbage(self):
        try:
            GraphOrchestrator._check_plan_sections("!!!@@@###")
        except Exception as e:
            pytest.fail(f"_check_plan_sections raised: {e}")

    def test_all_five_required_sections_in_constant(self):
        """Verify _REQUIRED_PLAN_SECTIONS has exactly 5 entries."""
        assert len(_REQUIRED_PLAN_SECTIONS) == 5

    def test_required_sections_names(self):
        names = {name for _, name in _REQUIRED_PLAN_SECTIONS}
        assert names == {"Goal", "Assumptions", "Steps", "Risk Assessment", "Test Impact"}


# ── _compute_plan_health ──────────────────────────────────────────────────────


class TestComputePlanHealth:
    def test_all_clean_returns_100(self):
        plan = _full_plan(n_steps=3, with_verify=True)
        score = GraphOrchestrator._compute_plan_health(
            plan_content=plan,
            bad_assumptions=[],
            plan_critique=None,
            section_issues=[],
        )
        assert score == 100

    def test_bad_assumptions_reduces_score(self):
        plan = _full_plan()
        score_clean = GraphOrchestrator._compute_plan_health(plan, [], None, [])
        score_bad = GraphOrchestrator._compute_plan_health(plan, ["file not found: x.py"], None, [])
        assert score_bad < score_clean
        assert score_clean - score_bad == 25

    def test_remaining_critique_reduces_score(self):
        plan = _full_plan()
        score_clean = GraphOrchestrator._compute_plan_health(plan, [], None, [])
        score_issues = GraphOrchestrator._compute_plan_health(
            plan, [], "**[Edge Cases]** missing timeout", []
        )
        assert score_issues < score_clean
        assert score_clean - score_issues == 25

    def test_section_issues_reduces_score(self):
        plan = _full_plan()
        score_clean = GraphOrchestrator._compute_plan_health(plan, [], None, [])
        score_missing = GraphOrchestrator._compute_plan_health(plan, [], None, ["Goal"])
        assert score_missing < score_clean
        assert score_clean - score_missing == 25

    def test_no_verify_lines_reduces_score(self):
        plan = _full_plan(n_steps=3, with_verify=False)
        score_no_verify = GraphOrchestrator._compute_plan_health(plan, [], None, [])
        # Plan has all sections but no Verify: lines → step format penalty
        assert score_no_verify <= 75

    def test_all_four_penalties_applied(self):
        """All four components missing → score 0 (or close to 0)."""
        bare_plan = "1. Do something"
        score = GraphOrchestrator._compute_plan_health(
            plan_content=bare_plan,
            bad_assumptions=["missing.py not found"],
            plan_critique="UNRESOLVED issues remain",
            section_issues=["Goal", "Assumptions", "Steps"],
        )
        assert score <= 25  # only possible partial credit from step format

    def test_score_is_int(self):
        assert isinstance(GraphOrchestrator._compute_plan_health("", [], None, []), int)

    def test_score_never_exceeds_100(self):
        plan = _full_plan(n_steps=10, with_verify=True)
        assert GraphOrchestrator._compute_plan_health(plan, [], None, []) <= 100

    def test_score_never_below_zero(self):
        assert GraphOrchestrator._compute_plan_health("", ["bad"], "critique", ["Goal"]) >= 0

    def test_no_steps_gives_partial_step_credit(self):
        """Plan with no numbered steps gets partial (not zero) step-format credit."""
        plan = "**Goal:** X\n**Assumptions:**\n- ok\n**Steps:** (none)\n**Risk Assessment:**\n**Test Impact:**\n"
        score = GraphOrchestrator._compute_plan_health(plan, [], None, [])
        # Section completeness: 25 (all headers present), assumptions: 25, critique: 25,
        # step format: 12 (partial) = 87
        assert score >= 75

    def test_never_raises_on_garbage(self):
        try:
            GraphOrchestrator._compute_plan_health("!!!###", ["x"], "critique", ["Goal"])
        except Exception as e:
            pytest.fail(f"_compute_plan_health raised: {e}")


# ── _verify_assumptions_node: plan_section_issues ─────────────────────────────


class TestVerifyAssumptionsNodeSectionIssues:
    def test_section_issues_stored_in_state(self):
        """After verify_assumptions, plan_section_issues is in returned state."""
        orch = _make_orch()
        plan = "**Steps:**\n1. Go\n   Verify: done\n   Deps: none"
        state = {
            "user_message": "task",
            "context": "",
            "plan_response": _make_plan_response(plan),
            "plan_assumptions": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._verify_assumptions_node(state))
        assert "plan_section_issues" in result
        assert isinstance(result["plan_section_issues"], list)

    def test_complete_plan_has_no_section_issues(self):
        orch = _make_orch()
        plan = _full_plan()
        state = {
            "user_message": "task",
            "context": "",
            "plan_response": _make_plan_response(plan),
            "plan_assumptions": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._verify_assumptions_node(state))
        assert result["plan_section_issues"] == []

    def test_incomplete_plan_has_section_issues(self):
        orch = _make_orch()
        plan = "## Plan\n1. Do something"
        state = {
            "user_message": "task",
            "context": "",
            "plan_response": _make_plan_response(plan),
            "plan_assumptions": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._verify_assumptions_node(state))
        assert len(result["plan_section_issues"]) > 0
        assert "Goal" in result["plan_section_issues"]

    def test_no_plan_response_returns_empty_section_issues(self):
        orch = _make_orch()
        state = {
            "user_message": "task",
            "context": "",
            "plan_response": None,
            "plan_assumptions": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._verify_assumptions_node(state))
        assert result.get("plan_section_issues") == []

    def test_section_issues_independent_of_assumption_status(self):
        """Section check runs even when there are no unverified assumptions."""
        orch = _make_orch()
        plan = "**Steps:**\n1. Go"  # no unverified assumptions but missing sections
        state = {
            "user_message": "task",
            "context": "",
            "plan_response": _make_plan_response(plan),
            "plan_assumptions": ["- Everything fine [✓ Verified]"],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._verify_assumptions_node(state))
        assert "plan_section_issues" in result
        # Goal, Assumptions, Risk Assessment, Test Impact are missing
        assert len(result["plan_section_issues"]) >= 3

    def test_plan_content_not_modified_by_section_check(self):
        """Section check is analysis-only — plan content is not modified."""
        orch = _make_orch()
        original_content = "**Steps:**\n1. Go"
        state = {
            "user_message": "task",
            "context": "",
            "plan_response": _make_plan_response(original_content),
            "plan_assumptions": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._verify_assumptions_node(state))
        # Plan content unchanged (no ## Plan Structure Issues appended)
        assert "Plan Structure Issues" not in result["plan_response"].content


# ── _approve_plan_node: health score ──────────────────────────────────────────


class TestApproveNodeHealthScore:
    def test_health_score_stored_in_state_on_auto_approve(self):
        orch = _make_orch()
        plan = _full_plan()
        state = {
            "user_message": "task",
            "context": "",
            "plan_response": _make_plan_response(plan),
            "plan_bad_assumptions": [],
            "plan_critique": None,
            "plan_section_issues": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        with patch.object(orch, "_save_approved_plan"):
            result = asyncio.run(orch._approve_plan_node(state))
        assert "plan_health_score" in result
        assert isinstance(result["plan_health_score"], int)

    def test_health_score_100_for_perfect_plan(self):
        orch = _make_orch()
        plan = _full_plan(n_steps=3, with_verify=True)
        state = {
            "user_message": "task",
            "context": "",
            "plan_response": _make_plan_response(plan),
            "plan_bad_assumptions": [],
            "plan_critique": None,
            "plan_section_issues": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        with patch.object(orch, "_save_approved_plan"):
            result = asyncio.run(orch._approve_plan_node(state))
        assert result["plan_health_score"] == 100

    def test_health_score_lower_with_bad_assumptions(self):
        orch = _make_orch()
        plan = _full_plan()
        state_clean = {
            "user_message": "task",
            "context": "",
            "plan_response": _make_plan_response(plan),
            "plan_bad_assumptions": [],
            "plan_critique": None,
            "plan_section_issues": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        state_bad = {
            **state_clean,
            "plan_bad_assumptions": ["missing.py not found"],
        }
        with patch.object(orch, "_save_approved_plan"):
            clean_result = asyncio.run(orch._approve_plan_node(state_clean))
            bad_result = asyncio.run(orch._approve_plan_node(state_bad))
        assert bad_result["plan_health_score"] < clean_result["plan_health_score"]

    def test_status_callback_fired_with_score(self):
        orch = _make_orch()
        status_calls: list[str] = []
        orch.set_status_callback(lambda s: status_calls.append(s))
        plan = _full_plan()
        state = {
            "user_message": "task",
            "context": "",
            "plan_response": _make_plan_response(plan),
            "plan_bad_assumptions": [],
            "plan_critique": None,
            "plan_section_issues": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        with patch.object(orch, "_save_approved_plan"):
            asyncio.run(orch._approve_plan_node(state))
        assert any("/100" in s for s in status_calls), f"status_calls={status_calls}"

    def test_status_callback_includes_quality_label(self):
        """Status message should include a human-readable label."""
        orch = _make_orch()
        status_calls: list[str] = []
        orch.set_status_callback(lambda s: status_calls.append(s))
        plan = _full_plan()
        state = {
            "user_message": "task",
            "context": "",
            "plan_response": _make_plan_response(plan),
            "plan_bad_assumptions": [],
            "plan_critique": None,
            "plan_section_issues": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        with patch.object(orch, "_save_approved_plan"):
            asyncio.run(orch._approve_plan_node(state))
        quality_msg = next((s for s in status_calls if "/100" in s), "")
        valid_labels = ("excellent", "good", "fair", "poor")
        assert any(label in quality_msg for label in valid_labels), f"msg={quality_msg!r}"

    def test_health_score_stored_on_rejection(self):
        orch = _make_orch()
        orch._clarification_handler = lambda p, c, ctx: "Reject"
        plan = _full_plan()
        state = {
            "user_message": "task",
            "context": "",
            "plan_response": _make_plan_response(plan),
            "plan_bad_assumptions": [],
            "plan_critique": None,
            "plan_section_issues": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._approve_plan_node(state))
        assert result["plan_approved"] is False
        assert "plan_health_score" in result
        assert isinstance(result["plan_health_score"], int)

    def test_health_score_zero_when_no_plan_response(self):
        orch = _make_orch()
        state = {
            "user_message": "task",
            "context": "",
            "plan_response": None,
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._approve_plan_node(state))
        assert result["plan_health_score"] == 0

    def test_health_score_stored_on_editor_reject(self):
        orch = _make_orch()
        orch.set_plan_editor(lambda text: None)
        plan = _full_plan()
        state = {
            "user_message": "task",
            "context": "",
            "plan_response": _make_plan_response(plan),
            "plan_bad_assumptions": [],
            "plan_critique": None,
            "plan_section_issues": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._approve_plan_node(state))
        assert result["plan_approved"] is False
        assert "plan_health_score" in result
