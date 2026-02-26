"""Tests for Task D: Auto-debug suggestion after 2+ tool failures."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.agents.base import AgentConfig, AgentResponse, BaseAgent, TokenUsage
from lidco.agents.graph import GraphOrchestrator
from lidco.agents.registry import AgentRegistry


# ── Helpers ───────────────────────────────────────────────────────────────────


class ConcreteAgent(BaseAgent):
    def get_system_prompt(self) -> str:
        return self._config.system_prompt


def _make_simple_agent(name: str, response_content: str = "done") -> ConcreteAgent:
    config = AgentConfig(
        name=name,
        description=name,
        system_prompt="sys",
        tools=[],
        max_iterations=1,
    )
    llm = MagicMock()
    from lidco.llm.base import LLMResponse
    llm.complete = AsyncMock(return_value=LLMResponse(
        content=response_content, model="m", tool_calls=[], usage={}, finish_reason="stop",
    ))
    registry = MagicMock()
    registry.list_tools.return_value = []
    return ConcreteAgent(config=config, llm=llm, tool_registry=registry)


def _make_orchestrator_with_mocked_graph(
    error_count_sequence: list[int],
    agent_name: str = "coder",
    response_content: str = "result",
) -> GraphOrchestrator:
    """Build a GraphOrchestrator whose graph.ainvoke is mocked to return a preset response."""
    llm = MagicMock()
    from lidco.llm.base import LLMResponse
    # Router response
    llm.complete = AsyncMock(return_value=LLMResponse(
        content=f'{{"agent": "{agent_name}", "needs_review": false, "needs_planning": false}}',
        model="m", tool_calls=[], usage={}, finish_reason="stop",
    ))

    reg = AgentRegistry()
    agent = _make_simple_agent(agent_name, response_content)
    reg.register(agent)

    orch = GraphOrchestrator(
        llm=llm,
        agent_registry=reg,
        auto_review=False,
        auto_plan=False,
        agent_timeout=0,
    )

    # Mock the entire graph.ainvoke so we control what state it returns
    final_state = {
        "agent_response": AgentResponse(
            content=response_content,
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

    # Simulate error count going up during the run
    call_count = [0]
    counts = error_count_sequence

    def _reader():
        idx = min(call_count[0], len(counts) - 1)
        val = counts[idx]
        call_count[0] += 1
        return val

    orch.set_error_count_reader(_reader)
    return orch


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestAutoDebugSuggestion:
    def test_advisory_appended_on_two_new_errors(self):
        # Before=0, after=2 → 2 new errors
        orch = _make_orchestrator_with_mocked_graph([0, 2], agent_name="coder")
        result = asyncio.run(orch.handle("do something"))
        assert "Debug tip" in result.content
        assert "/errors" in result.content

    def test_advisory_not_appended_on_one_error(self):
        # Before=0, after=1 → only 1 new error
        orch = _make_orchestrator_with_mocked_graph([0, 1], agent_name="coder")
        result = asyncio.run(orch.handle("do something"))
        assert "Debug tip" not in result.content

    def test_advisory_not_appended_on_zero_errors(self):
        orch = _make_orchestrator_with_mocked_graph([0, 0], agent_name="coder")
        result = asyncio.run(orch.handle("do something"))
        assert "Debug tip" not in result.content

    def test_advisory_not_appended_for_debugger_agent(self):
        # Even with 3 new errors, the debugger run should not get the advisory
        orch = _make_orchestrator_with_mocked_graph([0, 3], agent_name="debugger")
        result = asyncio.run(orch.handle("analyze", agent_name="debugger"))
        assert "Debug tip" not in result.content

    def test_advisory_appended_on_three_errors(self):
        orch = _make_orchestrator_with_mocked_graph([5, 8], agent_name="coder")
        result = asyncio.run(orch.handle("try it"))
        assert "Debug tip" in result.content

    def test_no_error_count_reader_no_advisory(self):
        llm = MagicMock()
        from lidco.llm.base import LLMResponse
        llm.complete = AsyncMock(return_value=LLMResponse(
            content='{"agent": "coder", "needs_review": false, "needs_planning": false}',
            model="m", tool_calls=[], usage={}, finish_reason="stop",
        ))
        reg = AgentRegistry()
        agent = _make_simple_agent("coder", "all done")
        reg.register(agent)

        orch = GraphOrchestrator(
            llm=llm, agent_registry=reg, auto_review=False, auto_plan=False, agent_timeout=0,
        )
        final_state = {
            "agent_response": AgentResponse(
                content="all done",
                tool_calls_made=[],
                iterations=1,
                model_used="m",
                token_usage=TokenUsage(),
            ),
            "selected_agent": "coder",
            "review_response": None,
            "medium_issues": "",
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        orch._graph = MagicMock()
        orch._graph.ainvoke = AsyncMock(return_value=final_state)
        # No error_count_reader set

        result = asyncio.run(orch.handle("go"))
        assert "Debug tip" not in result.content

    def test_original_content_preserved_with_advisory(self):
        orch = _make_orchestrator_with_mocked_graph([0, 2], agent_name="coder", response_content="main response")
        result = asyncio.run(orch.handle("do it"))
        assert "main response" in result.content
        assert "Debug tip" in result.content
