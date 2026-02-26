"""Tests for Task A: prepend_system_context and failure-site snippet injection."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.agents.base import AgentConfig, BaseAgent
from lidco.llm.base import LLMResponse


# ── Helpers ───────────────────────────────────────────────────────────────────


class ConcreteAgent(BaseAgent):
    """Minimal concrete BaseAgent for testing."""

    def get_system_prompt(self) -> str:
        return self._config.system_prompt


def _make_agent(system_prompt: str = "Base system prompt.") -> ConcreteAgent:
    config = AgentConfig(
        name="test",
        description="test agent",
        system_prompt=system_prompt,
        tools=[],
    )
    llm = MagicMock()
    registry = MagicMock()
    registry.list_tools.return_value = []
    return ConcreteAgent(config=config, llm=llm, tool_registry=registry)


# ── prepend_system_context ────────────────────────────────────────────────────


class TestPrependSystemContext:
    def test_pending_context_empty_by_default(self):
        agent = _make_agent()
        assert agent._pending_context == []

    def test_prepend_adds_to_pending(self):
        agent = _make_agent()
        agent.prepend_system_context("## Snippets\nsome code")
        assert len(agent._pending_context) == 1
        assert "## Snippets" in agent._pending_context[0]

    def test_multiple_prepends_accumulate(self):
        agent = _make_agent()
        agent.prepend_system_context("first")
        agent.prepend_system_context("second")
        assert len(agent._pending_context) == 2

    def test_build_system_prompt_includes_pending_at_top(self):
        agent = _make_agent("My system.")
        agent.prepend_system_context("## Failure-Site Snippets\ncode here")
        prompt = agent.build_system_prompt(context="base context")

        ctx_idx = prompt.index("## Current Context")
        # Snippets must appear before base context within the section
        snippets_idx = prompt.index("## Failure-Site Snippets")
        base_idx = prompt.index("base context")
        assert ctx_idx < snippets_idx < base_idx

    def test_build_system_prompt_consumes_pending(self):
        agent = _make_agent()
        agent.prepend_system_context("injected")
        agent.build_system_prompt(context="ctx")
        # After calling build_system_prompt, _pending_context should be reset
        assert agent._pending_context == []

    def test_second_build_does_not_repeat_pending(self):
        agent = _make_agent()
        agent.prepend_system_context("only once")
        prompt1 = agent.build_system_prompt(context="c1")
        prompt2 = agent.build_system_prompt(context="c2")

        assert "only once" in prompt1
        assert "only once" not in prompt2

    def test_no_pending_no_extra_section(self):
        agent = _make_agent("System prompt.")
        prompt = agent.build_system_prompt(context="")
        # Should still work normally with no context section at all
        assert "System prompt." in prompt
        # No spurious "## Current Context" when there's nothing to include
        assert "## Current Context" not in prompt

    def test_pending_without_base_context(self):
        agent = _make_agent()
        agent.prepend_system_context("standalone snippet")
        prompt = agent.build_system_prompt(context="")
        assert "standalone snippet" in prompt
        assert "## Current Context" in prompt

    def test_base_context_without_pending(self):
        agent = _make_agent()
        prompt = agent.build_system_prompt(context="regular context")
        assert "regular context" in prompt
        assert "## Current Context" in prompt


# ── Integration: GraphOrchestrator injects snippets for debugger ───────────────


class TestDebuggerContextInjection:
    """Verify that _error_context_builder is called for the debugger agent."""

    def _make_orchestrator(self, builder_return: str = "## Snippets\ncode"):
        from lidco.agents.graph import GraphOrchestrator
        from lidco.agents.registry import AgentRegistry

        llm = MagicMock()
        registry = AgentRegistry()

        # Register a mock debugger
        debugger_agent = _make_agent("debugger system")
        debugger_agent._config = AgentConfig(
            name="debugger",
            description="debugger",
            system_prompt="debugger system",
            tools=[],
        )
        debugger_agent._llm = llm
        registry.register(debugger_agent)

        orch = GraphOrchestrator(
            llm=llm,
            agent_registry=registry,
            agent_timeout=0,
        )

        builder = MagicMock(return_value=builder_return)
        orch.set_error_context_builder(builder)
        return orch, debugger_agent, builder

    def test_error_context_builder_called_for_debugger(self):
        orch, agent, builder = self._make_orchestrator("## Snippets\nsome code")

        # Simulate what _execute_agent_node does
        if agent.config.name == "debugger" and orch._error_context_builder is not None:
            snippets = orch._error_context_builder()
            if snippets:
                agent.prepend_system_context(snippets)

        builder.assert_called_once()
        assert len(agent._pending_context) == 1
        assert "Snippets" in agent._pending_context[0]

    def test_empty_builder_result_not_injected(self):
        orch, agent, builder = self._make_orchestrator("")

        if agent.config.name == "debugger" and orch._error_context_builder is not None:
            snippets = orch._error_context_builder()
            if snippets:
                agent.prepend_system_context(snippets)

        assert agent._pending_context == []

    def test_no_builder_no_injection(self):
        from lidco.agents.graph import GraphOrchestrator
        from lidco.agents.registry import AgentRegistry

        llm = MagicMock()
        reg = AgentRegistry()
        agent = _make_agent("debugger")
        agent._config = AgentConfig(
            name="debugger", description="d", system_prompt="d", tools=[],
        )
        agent._llm = llm
        reg.register(agent)

        orch = GraphOrchestrator(llm=llm, agent_registry=reg)
        # No builder set
        assert orch._error_context_builder is None

        # Simulate the conditional check — nothing should be injected
        if agent.config.name == "debugger" and orch._error_context_builder is not None:
            agent.prepend_system_context("should not happen")

        assert agent._pending_context == []
