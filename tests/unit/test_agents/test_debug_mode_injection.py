"""Tests for Task D: debug mode context injection for planning agents."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.agents.base import AgentConfig, AgentResponse, BaseAgent, TokenUsage
from lidco.agents.graph import GraphOrchestrator, _PLANNING_AGENTS
from lidco.agents.registry import AgentRegistry


# ── helpers ───────────────────────────────────────────────────────────────────


class ConcreteAgent(BaseAgent):
    def get_system_prompt(self) -> str:
        return self._config.system_prompt


def _make_agent(name: str) -> ConcreteAgent:
    config = AgentConfig(
        name=name,
        description=name,
        system_prompt="You are helpful.",
        tools=[],
        max_iterations=1,
    )
    llm = MagicMock()
    from lidco.llm.base import LLMResponse
    llm.complete = AsyncMock(return_value=LLMResponse(
        content="done",
        model="m",
        tool_calls=[],
        usage={},
        finish_reason="stop",
    ))
    registry = MagicMock()
    registry.list_tools.return_value = []
    return ConcreteAgent(config=config, llm=llm, tool_registry=registry)


def _make_orchestrator(agent_name: str) -> tuple[GraphOrchestrator, list[str]]:
    """Build a GraphOrchestrator with a mocked graph and return it with a
    captured list of contexts injected into the agent's pending_context."""
    llm = MagicMock()
    from lidco.llm.base import LLMResponse
    llm.complete = AsyncMock(return_value=LLMResponse(
        content=f'{{"agent": "{agent_name}", "needs_review": false, "needs_planning": false}}',
        model="m", tool_calls=[], usage={}, finish_reason="stop",
    ))

    reg = AgentRegistry()
    agent = _make_agent(agent_name)
    reg.register(agent)

    orch = GraphOrchestrator(
        llm=llm,
        agent_registry=reg,
        auto_review=False,
        auto_plan=False,
        agent_timeout=0,
    )

    injected: list[str] = []

    # Intercept prepend_system_context
    original_run = agent.run

    async def _patched_run(msg, context=""):
        injected.extend(agent._pending_context)
        agent._pending_context = []  # reset so it doesn't affect the actual run
        return await original_run(msg, context=context)

    agent.run = _patched_run  # type: ignore

    final_state = {
        "agent_response": AgentResponse(
            content="result",
            tool_calls_made=[],
            iterations=1,
            model_used="m",
            token_usage=TokenUsage(),
        ),
        "selected_agent": agent_name,
        "review_response": None,
        "medium_issues": "",
        "accumulated_tokens": 0,
        "accumulated_cost_usd": 0.0,
    }
    orch._graph = MagicMock()
    orch._graph.ainvoke = AsyncMock(return_value=final_state)

    return orch, injected


# ── set_debug_mode setter ─────────────────────────────────────────────────────


class TestSetDebugMode:
    def test_default_is_false(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        assert orch._debug_mode is False

    def test_set_debug_mode_true(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        orch.set_debug_mode(True)
        assert orch._debug_mode is True

    def test_set_debug_mode_false(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        orch.set_debug_mode(True)
        orch.set_debug_mode(False)
        assert orch._debug_mode is False


# ── set_error_summary_builder setter ─────────────────────────────────────────


class TestSetErrorSummaryBuilder:
    def test_default_is_none(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        assert orch._error_summary_builder is None

    def test_setter_stores_callable(self):
        llm = MagicMock()
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        fn = lambda: "## Recent Errors\n- some error"
        orch.set_error_summary_builder(fn)
        assert orch._error_summary_builder is fn


# ── context injection ─────────────────────────────────────────────────────────


class TestDebugContextInjection:
    def _setup(
        self,
        agent_name: str,
        debug_mode: bool,
        error_summary: str,
    ) -> tuple[GraphOrchestrator, list[str]]:
        orch, injected = _make_orchestrator(agent_name)
        orch.set_debug_mode(debug_mode)
        orch.set_error_summary_builder(lambda: error_summary)
        return orch, injected

    def test_coder_gets_debug_context_when_debug_mode_on(self):
        orch, injected = _make_orchestrator("coder")
        orch.set_debug_mode(True)
        orch.set_error_summary_builder(lambda: "## Recent Errors\n- bash failed")

        # We need to test _execute_agent_node directly since graph is mocked
        agent = orch._registry.get("coder")
        captured: list[str] = []
        original = agent.prepend_system_context

        def _capture(text: str) -> None:
            captured.append(text)
            original(text)

        agent.prepend_system_context = _capture  # type: ignore

        # Build minimal state and call the node
        state = {
            "user_message": "fix this",
            "context": "",
            "selected_agent": "coder",
            "review_iteration": 0,
            "conversation_history": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        asyncio.run(orch._execute_agent_node(state))

        assert any("Active Debug Context" in t for t in captured)

    def test_no_injection_when_debug_mode_off(self):
        orch, _ = _make_orchestrator("coder")
        orch.set_debug_mode(False)
        orch.set_error_summary_builder(lambda: "## Recent Errors\n- error")

        agent = orch._registry.get("coder")
        captured: list[str] = []
        original = agent.prepend_system_context

        def _capture(text: str) -> None:
            captured.append(text)
            original(text)

        agent.prepend_system_context = _capture  # type: ignore

        state = {
            "user_message": "fix this",
            "context": "",
            "selected_agent": "coder",
            "review_iteration": 0,
            "conversation_history": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        asyncio.run(orch._execute_agent_node(state))
        assert not any("Active Debug Context" in t for t in captured)

    def test_no_injection_when_summary_empty(self):
        orch, _ = _make_orchestrator("coder")
        orch.set_debug_mode(True)
        orch.set_error_summary_builder(lambda: "")  # empty summary

        agent = orch._registry.get("coder")
        captured: list[str] = []
        original = agent.prepend_system_context

        def _capture(text: str) -> None:
            captured.append(text)
            original(text)

        agent.prepend_system_context = _capture  # type: ignore

        state = {
            "user_message": "fix this",
            "context": "",
            "selected_agent": "coder",
            "review_iteration": 0,
            "conversation_history": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        asyncio.run(orch._execute_agent_node(state))
        assert not any("Active Debug Context" in t for t in captured)

    def test_no_injection_when_no_summary_builder(self):
        orch, _ = _make_orchestrator("coder")
        orch.set_debug_mode(True)
        # No summary builder set

        agent = orch._registry.get("coder")
        captured: list[str] = []
        original = agent.prepend_system_context

        def _capture(text: str) -> None:
            captured.append(text)
            original(text)

        agent.prepend_system_context = _capture  # type: ignore

        state = {
            "user_message": "fix this",
            "context": "",
            "selected_agent": "coder",
            "review_iteration": 0,
            "conversation_history": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        asyncio.run(orch._execute_agent_node(state))
        assert not any("Active Debug Context" in t for t in captured)

    def test_debugger_does_not_get_duplicate_advisory(self):
        """Debugger gets snippet injection, NOT the planning-agent advisory."""
        orch, _ = _make_orchestrator("debugger")
        orch.set_debug_mode(True)
        orch.set_error_summary_builder(lambda: "## Recent Errors\n- boom")
        orch.set_error_context_builder(lambda: "")  # no snippets

        agent = orch._registry.get("debugger")
        captured: list[str] = []
        original = agent.prepend_system_context

        def _capture(text: str) -> None:
            captured.append(text)
            original(text)

        agent.prepend_system_context = _capture  # type: ignore

        state = {
            "user_message": "debug this",
            "context": "",
            "selected_agent": "debugger",
            "review_iteration": 0,
            "conversation_history": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        asyncio.run(orch._execute_agent_node(state))
        assert not any("Active Debug Context" in t for t in captured)

    def test_reviewer_not_a_planning_agent_no_injection(self):
        """reviewer is NOT in _PLANNING_AGENTS — no injection even in debug mode."""
        assert "reviewer" not in _PLANNING_AGENTS

        orch, _ = _make_orchestrator("reviewer")
        orch.set_debug_mode(True)
        orch.set_error_summary_builder(lambda: "## Recent Errors\n- error")

        # Add a reviewer agent to the registry
        reviewer = _make_agent("reviewer")
        orch._registry.register(reviewer)

        captured: list[str] = []
        original = reviewer.prepend_system_context

        def _capture(text: str) -> None:
            captured.append(text)
            original(text)

        reviewer.prepend_system_context = _capture  # type: ignore

        state = {
            "user_message": "review this",
            "context": "",
            "selected_agent": "reviewer",
            "review_iteration": 0,
            "conversation_history": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        asyncio.run(orch._execute_agent_node(state))
        assert not any("Active Debug Context" in t for t in captured)

    def test_planning_agents_in_frozenset(self):
        """Sanity check — key agents are in the planning agents set."""
        for name in ("coder", "tester", "refactor"):
            assert name in _PLANNING_AGENTS
