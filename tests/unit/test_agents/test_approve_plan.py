"""Tests for _approve_plan_node in GraphOrchestrator."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from lidco.agents.base import AgentResponse, TokenUsage
from lidco.agents.graph import GraphOrchestrator
from lidco.agents.registry import AgentRegistry


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_plan_response(content: str) -> AgentResponse:
    return AgentResponse(
        content=content,
        tool_calls_made=[],
        iterations=2,
        model_used="test-model",
        token_usage=TokenUsage(total_tokens=100, total_cost_usd=0.01),
    )


def _make_orch() -> GraphOrchestrator:
    llm = MagicMock()
    reg = AgentRegistry()
    return GraphOrchestrator(llm=llm, agent_registry=reg, agent_timeout=0)


def _base_state(plan_content: str = "## Plan\n1. Do A\n2. Do B") -> dict:
    return {
        "user_message": "add feature X",
        "context": "",
        "plan_response": _make_plan_response(plan_content),
        "accumulated_tokens": 0,
        "accumulated_cost_usd": 0.0,
    }


# ── plan editor path ───────────────────────────────────────────────────────────


class TestAprovePlanEditorPath:
    def test_editor_returns_filtered_plan_approved(self):
        """When editor returns a string, plan is approved with merged context."""
        orch = _make_orch()
        orch.set_plan_editor(lambda text: "1. Filtered step")
        # Patch _save_approved_plan to avoid disk access
        with patch.object(orch, "_save_approved_plan"):
            result = asyncio.run(orch._approve_plan_node(_base_state()))
        assert result["plan_approved"] is True
        assert "Filtered step" in result.get("context", "")

    def test_editor_returns_none_plan_rejected(self):
        """When editor returns None, plan is rejected."""
        orch = _make_orch()
        orch.set_plan_editor(lambda text: None)
        result = asyncio.run(orch._approve_plan_node(_base_state()))
        assert result["plan_approved"] is False

    def test_editor_exception_auto_approves(self):
        """When editor raises, plan is auto-approved."""
        orch = _make_orch()
        orch.set_plan_editor(lambda text: (_ for _ in ()).throw(RuntimeError("crash")))
        result = asyncio.run(orch._approve_plan_node(_base_state()))
        assert result["plan_approved"] is True

    def test_editor_exception_calls_report_status(self):
        """When editor raises, _report_status is called with an error message."""
        orch = _make_orch()
        status_calls: list[str] = []
        orch.set_status_callback(lambda msg: status_calls.append(msg))

        def failing_editor(text: str) -> str:
            raise RuntimeError("editor crashed")

        orch.set_plan_editor(failing_editor)
        asyncio.run(orch._approve_plan_node(_base_state()))
        assert any("error" in s.lower() or "auto-approv" in s.lower() for s in status_calls)

    def test_editor_exception_parallel_steps_empty(self):
        """Auto-approve on editor failure still parses parallel steps."""
        orch = _make_orch()
        orch.set_plan_editor(lambda text: (_ for _ in ()).throw(RuntimeError("x")))
        state = _base_state("## Plan\n1. [PARALLEL] step A\n2. [PARALLEL] step B")
        result = asyncio.run(orch._approve_plan_node(state))
        # parallel_steps should be populated from the original plan text
        assert "parallel_steps" in result


# ── no plan editor, no clarification handler ──────────────────────────────────


class TestApprovePlanNoHandlers:
    def test_no_handlers_auto_approves(self):
        """With no editor and no clarification handler, plan is auto-approved."""
        orch = _make_orch()
        with patch.object(orch, "_save_approved_plan"):
            result = asyncio.run(orch._approve_plan_node(_base_state()))
        assert result["plan_approved"] is True

    def test_no_plan_response_auto_approves(self):
        """When state has no plan_response, node passes through approved."""
        orch = _make_orch()
        state = {
            "user_message": "x",
            "context": "",
            "plan_response": None,
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._approve_plan_node(state))
        assert result["plan_approved"] is True


# ── clarification handler path ─────────────────────────────────────────────────


class TestApprovePlanClarificationHandler:
    def test_approve_answer_approves_plan(self):
        """Handler returning 'Approve' results in plan_approved=True."""
        orch = _make_orch()
        orch._clarification_handler = lambda prompt, choices, content: "Approve"
        with patch.object(orch, "_save_approved_plan"):
            result = asyncio.run(orch._approve_plan_node(_base_state()))
        assert result["plan_approved"] is True

    def test_reject_answer_rejects_plan(self):
        """Handler returning 'Reject' results in plan_approved=False."""
        orch = _make_orch()
        orch._clarification_handler = lambda prompt, choices, content: "Reject"
        result = asyncio.run(orch._approve_plan_node(_base_state()))
        assert result["plan_approved"] is False

    def test_handler_exception_auto_approves(self):
        """When clarification handler raises, plan is auto-approved."""
        orch = _make_orch()

        def failing_handler(prompt, choices, content):
            raise RuntimeError("handler error")

        orch._clarification_handler = failing_handler
        with patch.object(orch, "_save_approved_plan"):
            result = asyncio.run(orch._approve_plan_node(_base_state()))
        assert result["plan_approved"] is True

    def test_handler_exception_calls_report_status(self):
        """When clarification handler raises, _report_status is called."""
        orch = _make_orch()
        status_calls: list[str] = []
        orch.set_status_callback(lambda msg: status_calls.append(msg))

        def failing_handler(prompt, choices, content):
            raise RuntimeError("handler crash")

        orch._clarification_handler = failing_handler
        with patch.object(orch, "_save_approved_plan"):
            asyncio.run(orch._approve_plan_node(_base_state()))
        assert any("error" in s.lower() or "auto-approv" in s.lower() for s in status_calls)
