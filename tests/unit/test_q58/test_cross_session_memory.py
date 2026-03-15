"""Tests for BaseAgent cross-session memory — Task 395."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lidco.agents.base import AgentConfig, BaseAgent
from lidco.tools.registry import ToolRegistry


class _ConcreteAgent(BaseAgent):
    """Minimal concrete subclass for testing."""

    def get_system_prompt(self) -> str:
        return "You are a helpful assistant."


def _make_agent(name: str = "coder") -> _ConcreteAgent:
    config = AgentConfig(name=name, description="test", system_prompt="base prompt")
    llm = MagicMock()
    registry = ToolRegistry()
    return _ConcreteAgent(config=config, llm=llm, tool_registry=registry)


def _make_memory_store(entries: list[str] | None = None) -> MagicMock:
    """Build a fake MemoryStore that returns given entries."""
    from lidco.core.memory import MemoryEntry

    store = MagicMock()
    mem_entries = [
        MemoryEntry(key=f"k{i}", content=c, category=f"agent_coder")
        for i, c in enumerate(entries or [])
    ]
    store.search.return_value = mem_entries
    store.add.return_value = None
    return store


class TestCrossSessionMemoryInit:
    def test_cross_session_memory_initialized_empty(self):
        agent = _make_agent()
        assert agent._cross_session_memory == []


class TestLoadCrossSessionMemory:
    def test_load_populates_memory(self):
        agent = _make_agent()
        store = _make_memory_store(["use pytest fixtures", "avoid mutable defaults"])
        agent.load_cross_session_memory(store)
        assert len(agent._cross_session_memory) == 2
        assert "use pytest fixtures" in agent._cross_session_memory

    def test_load_calls_search_with_agent_category(self):
        agent = _make_agent("security")
        store = _make_memory_store([])
        agent.load_cross_session_memory(store)
        store.search.assert_called_once()
        # Verify the category keyword arg contains the agent name
        call_obj = store.search.call_args
        # call_args has .kwargs dict for keyword args
        all_kwargs = call_obj.kwargs if hasattr(call_obj, "kwargs") else {}
        category_arg = all_kwargs.get("category", "")
        assert "security" in str(category_arg)

    def test_load_handles_exception_gracefully(self):
        agent = _make_agent()
        store = MagicMock()
        store.search.side_effect = RuntimeError("db error")
        agent.load_cross_session_memory(store)  # must not raise
        assert agent._cross_session_memory == []

    def test_load_limits_to_top_3(self):
        agent = _make_agent()
        store = _make_memory_store(["a", "b", "c"])
        # store.search already returns 3; test that limit param is passed
        agent.load_cross_session_memory(store)
        call_kwargs = store.search.call_args
        limit = call_kwargs.kwargs.get("limit")
        assert limit == 3


class TestSaveCrossSessionDecision:
    def test_save_calls_memory_store_add(self):
        agent = _make_agent()
        store = _make_memory_store()
        agent.save_cross_session_decision(store, "always use type hints")
        store.add.assert_called_once()

    def test_save_uses_agent_category(self):
        agent = _make_agent("architect")
        store = _make_memory_store()
        agent.save_cross_session_decision(store, "prefer event sourcing")
        call_kwargs = store.add.call_args
        category = call_kwargs.kwargs.get("category") or ""
        assert "architect" in category

    def test_save_handles_exception_gracefully(self):
        agent = _make_agent()
        store = MagicMock()
        store.add.side_effect = OSError("disk full")
        agent.save_cross_session_decision(store, "decision")  # must not raise


class TestBuildSystemPromptWithMemory:
    def test_past_decisions_injected_into_prompt(self):
        agent = _make_agent()
        agent._cross_session_memory = ["prefer composition over inheritance", "use factory pattern"]
        prompt = agent.build_system_prompt()
        assert "## Past Decisions" in prompt
        assert "prefer composition over inheritance" in prompt
        assert "use factory pattern" in prompt

    def test_no_past_decisions_section_when_empty(self):
        agent = _make_agent()
        agent._cross_session_memory = []
        prompt = agent.build_system_prompt()
        assert "## Past Decisions" not in prompt

    def test_context_still_injected_alongside_memory(self):
        agent = _make_agent()
        agent._cross_session_memory = ["memory item"]
        prompt = agent.build_system_prompt(context="some project context")
        assert "## Past Decisions" in prompt
        assert "## Current Context" in prompt
        assert "some project context" in prompt

    def test_memory_appears_before_context(self):
        agent = _make_agent()
        agent._cross_session_memory = ["old decision"]
        prompt = agent.build_system_prompt(context="current ctx")
        decisions_pos = prompt.index("## Past Decisions")
        context_pos = prompt.index("## Current Context")
        assert decisions_pos < context_pos
