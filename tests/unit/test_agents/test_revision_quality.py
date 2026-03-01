"""Tests for plan revision quality improvements:
- _revise_plan_node updates plan_assumptions and saves plan_critique_addressed
- _re_critique_plan_node uses _RE_CRITIQUE_SYSTEM_PROMPT and passes original critique
- _RE_CRITIQUE_SYSTEM_PROMPT content and clean-pass normalization
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.agents.base import AgentResponse, TokenUsage
from lidco.agents.graph import GraphOrchestrator, _RE_CRITIQUE_SYSTEM_PROMPT
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


def _make_orch(llm_response: str = "All critique points addressed.") -> GraphOrchestrator:
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=LLMResponse(
        content=llm_response,
        model="cheap",
        tool_calls=[],
        usage={"total_tokens": 50},
        finish_reason="stop",
        cost_usd=0.001,
    ))
    reg = AgentRegistry()
    return GraphOrchestrator(llm=llm, agent_registry=reg, agent_timeout=0)


# ── _RE_CRITIQUE_SYSTEM_PROMPT content ───────────────────────────────────────


class TestReCritiqueSystemPrompt:
    def test_contains_unresolved_marker(self):
        assert "UNRESOLVED" in _RE_CRITIQUE_SYSTEM_PROMPT

    def test_contains_all_addressed_pass_message(self):
        assert "All critique points addressed" in _RE_CRITIQUE_SYSTEM_PROMPT

    def test_instructs_not_to_find_new_issues(self):
        assert "NOT" in _RE_CRITIQUE_SYSTEM_PROMPT.upper()

    def test_references_original_critique(self):
        assert "original critique" in _RE_CRITIQUE_SYSTEM_PROMPT.lower()


# ── _revise_plan_node: plan_assumptions updated ───────────────────────────────


class TestRevisionUpdatesAssumptions:
    _REVISED_PLAN = """\
## Implementation Plan

**Goal:** Fix retry logic.

**Assumptions:**
- retrier.py exists ✓ Verified by file_read
- Tests cover retry paths ✓ Verified by find_test_gaps

**Steps:**
1. [Easy | Files: retrier.py] Add back-off — no deps
"""

    def test_plan_assumptions_updated_after_revision(self):
        orch = _make_orch(self._REVISED_PLAN)
        state = {
            "user_message": "fix retry logic",
            "plan_response": _make_plan_response("## Old Plan\n1. Step"),
            "plan_critique": "**[Edge Cases]** missing back-off",
            "plan_assumptions": ["old assumption no longer valid"],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._revise_plan_node(state))

        assumptions = result.get("plan_assumptions", [])
        assert any("retrier.py" in a for a in assumptions)
        assert not any("old assumption" in a for a in assumptions)

    def test_assumptions_empty_when_revised_plan_has_none(self):
        revised_without_assumptions = "## Implementation Plan\n**Goal:** X\n**Steps:**\n1. Step"
        orch = _make_orch(revised_without_assumptions)
        state = {
            "user_message": "do X",
            "plan_response": _make_plan_response("## Old Plan\n1. Step"),
            "plan_critique": "some issue",
            "plan_assumptions": ["stale assumption"],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._revise_plan_node(state))

        # Revised plan has no Assumptions section — should return empty list
        assert result.get("plan_assumptions") == []


# ── _revise_plan_node: plan_critique_addressed saved ─────────────────────────


class TestRevisionSavesCritiqueAddressed:
    def test_plan_critique_addressed_saved(self):
        original_critique = "**[Edge Cases]** missing timeout in retrier.py"
        orch = _make_orch("## Implementation Plan\n**Goal:** x\n**Steps:**\n1. step")
        state = {
            "user_message": "fix retry",
            "plan_response": _make_plan_response("## Old Plan\n1. Step"),
            "plan_critique": original_critique,
            "plan_assumptions": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._revise_plan_node(state))

        assert result.get("plan_critique_addressed") == original_critique

    def test_plan_critique_cleared_after_revision(self):
        orch = _make_orch("## Implementation Plan\n**Goal:** x\n**Steps:**\n1. step")
        state = {
            "user_message": "fix retry",
            "plan_response": _make_plan_response("## Old Plan\n1. Step"),
            "plan_critique": "some critique",
            "plan_assumptions": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._revise_plan_node(state))

        assert result.get("plan_critique") is None


# ── _re_critique_plan_node: uses _RE_CRITIQUE_SYSTEM_PROMPT ──────────────────


class TestReCritiqueUsesNewPrompt:
    def test_re_critique_system_prompt_sent(self):
        orch = _make_orch("All critique points addressed.")
        state = {
            "plan_response": _make_plan_response("## Revised Plan\n1. Step"),
            "plan_critique_addressed": "**[Edge Cases]** missing timeout",
            "plan_revision_round": 0,
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        asyncio.run(orch._re_critique_plan_node(state))

        call_args = orch._llm.complete.call_args
        messages = call_args[0][0]
        system_msg = next((m for m in messages if m.role == "system"), None)
        assert system_msg is not None
        assert "UNRESOLVED" in system_msg.content or "original critique" in system_msg.content.lower()

    def test_original_critique_passed_in_user_content(self):
        orch = _make_orch("All critique points addressed.")
        state = {
            "plan_response": _make_plan_response("## Revised Plan\n1. Step"),
            "plan_critique_addressed": "**[Breaking Changes]** callers not listed",
            "plan_revision_round": 0,
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        asyncio.run(orch._re_critique_plan_node(state))

        call_args = orch._llm.complete.call_args
        messages = call_args[0][0]
        user_msg = next((m for m in messages if m.role == "user"), None)
        assert user_msg is not None
        assert "callers not listed" in user_msg.content
        assert "Original Critique" in user_msg.content


# ── _re_critique_plan_node: clean-pass normalization ─────────────────────────


class TestReCritiqueCleanPass:
    def test_all_addressed_sets_plan_critique_to_none(self):
        orch = _make_orch("All critique points addressed.")
        state = {
            "plan_response": _make_plan_response("## Revised Plan\n1. Step"),
            "plan_critique_addressed": "some critique",
            "plan_revision_round": 0,
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._re_critique_plan_node(state))

        assert result.get("plan_critique") is None

    def test_unresolved_issues_set_plan_critique(self):
        orch = _make_orch(
            "[UNRESOLVED] **[Edge Cases]** `retry.py:retry()` — timeout still missing."
        )
        state = {
            "plan_response": _make_plan_response("## Revised Plan\n1. Step"),
            "plan_critique_addressed": "**[Edge Cases]** timeout missing",
            "plan_revision_round": 0,
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._re_critique_plan_node(state))

        assert result.get("plan_critique") is not None
        assert "UNRESOLVED" in result["plan_critique"]

    def test_revision_round_incremented(self):
        orch = _make_orch("All critique points addressed.")
        state = {
            "plan_response": _make_plan_response("## Plan\n1. Step"),
            "plan_critique_addressed": "some critique",
            "plan_revision_round": 1,
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._re_critique_plan_node(state))

        assert result["plan_revision_round"] == 2

    def test_should_revise_again_exits_on_all_addressed(self):
        """_should_revise_again must return 'done' when re-critique is clean pass."""
        orch = _make_orch()
        state = {
            "plan_critique": None,  # cleared by clean pass
            "plan_revision_round": 0,
        }
        assert orch._should_revise_again(state) == "done"
