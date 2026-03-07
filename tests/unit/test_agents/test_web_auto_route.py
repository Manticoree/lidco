"""Tests for research query auto-routing (Q32, Task 148)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.agents.graph import GraphOrchestrator, _RESEARCH_SIGNALS
from lidco.agents.registry import AgentRegistry
from lidco.llm.base import BaseLLMProvider, LLMResponse


def _make_orch(web_auto_route: bool = True) -> GraphOrchestrator:
    llm = MagicMock(spec=BaseLLMProvider)
    registry = MagicMock(spec=AgentRegistry)
    registry.list_agents.return_value = []
    orch = GraphOrchestrator(llm=llm, agent_registry=registry)
    orch.set_web_auto_route(web_auto_route)
    return orch


class TestResearchSignals:
    def test_research_signals_frozenset_exists(self):
        assert isinstance(_RESEARCH_SIGNALS, frozenset)
        assert len(_RESEARCH_SIGNALS) >= 5

    def test_required_signals_present(self):
        required = {"research", "find", "search", "what is", "how does", "explain", "documentation"}
        for sig in required:
            assert sig in _RESEARCH_SIGNALS, f"{sig!r} not in _RESEARCH_SIGNALS"

    def test_signals_are_lowercase(self):
        for s in _RESEARCH_SIGNALS:
            assert s == s.lower(), f"Signal {s!r} is not lowercase"


class TestWebAutoRoute:
    def test_set_web_auto_route_true(self):
        orch = _make_orch()
        orch.set_web_auto_route(True)
        assert orch._web_auto_route_enabled is True

    def test_set_web_auto_route_false(self):
        orch = _make_orch()
        orch.set_web_auto_route(False)
        assert orch._web_auto_route_enabled is False

    def test_default_is_true(self):
        llm = MagicMock(spec=BaseLLMProvider)
        registry = MagicMock(spec=AgentRegistry)
        registry.list_agents.return_value = []
        orch = GraphOrchestrator(llm=llm, agent_registry=registry)
        assert orch._web_auto_route_enabled is True

    @pytest.mark.asyncio
    async def test_two_signals_routes_to_researcher(self):
        orch = _make_orch(web_auto_route=True)

        # researcher agent must exist in registry
        researcher_agent = MagicMock()
        researcher_agent.name = "researcher"
        researcher_agent.description = "Research agent"
        researcher_agent.config = MagicMock()
        researcher_agent.config.routing_keywords = []

        orch._registry.get.side_effect = lambda name: researcher_agent if name == "researcher" else None
        orch._registry.list_agents.return_value = [researcher_agent]

        state = {
            "user_message": "find documentation for asyncio and research best practices",
            "context": "",
            "selected_agent": "",
        }

        new_state = await orch._route_node(state)
        assert new_state["selected_agent"] == "researcher"

    @pytest.mark.asyncio
    async def test_one_signal_falls_through_to_llm(self):
        orch = _make_orch(web_auto_route=True)

        coder_agent = MagicMock()
        coder_agent.name = "coder"
        coder_agent.description = "Coder agent"
        coder_agent.config = MagicMock()
        coder_agent.config.routing_keywords = []

        orch._registry.get.side_effect = lambda name: coder_agent if name == "coder" else None
        orch._registry.list_agents.return_value = [coder_agent]

        # LLM returns coder
        resp = MagicMock()
        resp.content = '{"agent": "coder", "needs_review": false, "needs_planning": false}'
        orch._llm.complete = AsyncMock(return_value=resp)

        state = {
            "user_message": "find the bug in my code",  # only 1 signal: "find"
            "context": "",
            "selected_agent": "",
        }

        new_state = await orch._route_node(state)
        # Should NOT auto-route to researcher with only 1 signal
        assert new_state["selected_agent"] == "coder"

    @pytest.mark.asyncio
    async def test_disabled_flag_skips_auto_route(self):
        orch = _make_orch(web_auto_route=False)

        researcher_agent = MagicMock()
        researcher_agent.name = "researcher"
        researcher_agent.description = "Research agent"
        researcher_agent.config = MagicMock()
        researcher_agent.config.routing_keywords = []

        coder_agent = MagicMock()
        coder_agent.name = "coder"
        coder_agent.description = "Coder agent"
        coder_agent.config = MagicMock()
        coder_agent.config.routing_keywords = []

        orch._registry.get.side_effect = lambda name: (
            researcher_agent if name == "researcher" else
            coder_agent if name == "coder" else None
        )
        orch._registry.list_agents.return_value = [researcher_agent, coder_agent]

        resp = MagicMock()
        resp.content = '{"agent": "coder", "needs_review": false, "needs_planning": false}'
        orch._llm.complete = AsyncMock(return_value=resp)

        state = {
            "user_message": "research find documentation and explain how asyncio works",
            "context": "",
            "selected_agent": "",
        }

        new_state = await orch._route_node(state)
        # With flag disabled, should NOT auto-route
        assert new_state["selected_agent"] != "researcher"

    @pytest.mark.asyncio
    async def test_already_researcher_not_re_routed(self):
        orch = _make_orch(web_auto_route=True)

        researcher_agent = MagicMock()
        researcher_agent.name = "researcher"
        researcher_agent.description = "Research agent"
        researcher_agent.config = MagicMock()
        researcher_agent.config.routing_keywords = []

        orch._registry.get.side_effect = lambda name: researcher_agent if name == "researcher" else None
        orch._registry.list_agents.return_value = [researcher_agent]

        resp = MagicMock()
        resp.content = '{"agent": "researcher", "needs_review": false, "needs_planning": false}'
        orch._llm.complete = AsyncMock(return_value=resp)

        state = {
            "user_message": "research and find documentation and explain best practices",
            "context": "",
            "selected_agent": "",
        }

        new_state = await orch._route_node(state)
        # researcher routes to researcher — no double-routing issue
        assert new_state["selected_agent"] == "researcher"

    @pytest.mark.asyncio
    async def test_pre_selected_agent_skips_routing(self):
        """When selected_agent is already set, _route_node returns early."""
        orch = _make_orch(web_auto_route=True)
        orch._registry.list_agents.return_value = []

        state = {
            "user_message": "research find documentation and explain",
            "context": "",
            "selected_agent": "coder",  # already pre-selected
        }

        new_state = await orch._route_node(state)
        # Pre-selected agent is preserved unchanged
        assert new_state["selected_agent"] == "coder"

    def test_signal_count_threshold(self):
        """Verify that at least 2 signals must match."""
        orch = _make_orch(web_auto_route=True)
        msg_2_signals = "research documentation for asyncio"
        msg_1_signal = "find the bug"

        count_2 = sum(1 for sig in _RESEARCH_SIGNALS if sig in msg_2_signals.lower())
        count_1 = sum(1 for sig in _RESEARCH_SIGNALS if sig in msg_1_signal.lower())

        assert count_2 >= 2
        assert count_1 < 2
