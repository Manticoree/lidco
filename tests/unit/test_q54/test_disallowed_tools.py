"""Q54/362 — disallowed_tools enforcement in BaseAgent._get_tools()."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock


def _make_tool(name: str) -> MagicMock:
    t = MagicMock()
    t.name = name
    return t


def _make_agent(tools_cfg: list[str], disallowed: list[str], registry_tools: list[str]):
    from lidco.agents.base import AgentConfig, BaseAgent

    registry = MagicMock()
    registry.list_tools.return_value = [_make_tool(n) for n in registry_tools]
    registry.schema_version = 0

    cfg = AgentConfig(
        name="test",
        description="test",
        system_prompt="you are a test agent",
        tools=tools_cfg,
        disallowed_tools=disallowed,
    )

    class _TestAgent(BaseAgent):
        def get_system_prompt(self) -> str:
            return "test"

    agent = object.__new__(_TestAgent)
    agent._config = cfg
    agent._tool_registry = registry
    agent._tool_schemas_cache = None
    agent._schema_cache_version = -1
    return agent


class TestDisallowedTools:
    def test_allowlist_only_filters_correctly(self):
        agent = _make_agent(["read", "write"], [], ["read", "write", "bash"])
        tools = agent._get_tools()
        assert {t.name for t in tools} == {"read", "write"}

    def test_denylist_only_removes_tools(self):
        agent = _make_agent([], ["bash"], ["read", "write", "bash"])
        tools = agent._get_tools()
        assert {t.name for t in tools} == {"read", "write"}

    def test_both_allowlist_and_denylist(self):
        agent = _make_agent(["read", "write", "bash"], ["bash"], ["read", "write", "bash", "exec"])
        tools = agent._get_tools()
        assert {t.name for t in tools} == {"read", "write"}

    def test_empty_config_returns_all(self):
        agent = _make_agent([], [], ["read", "write", "bash"])
        tools = agent._get_tools()
        assert {t.name for t in tools} == {"read", "write", "bash"}

    def test_denylist_on_full_registry(self):
        """disallowed_tools blocks even when no allowlist is set."""
        agent = _make_agent([], ["bash", "exec"], ["read", "write", "bash", "exec"])
        tools = agent._get_tools()
        assert "bash" not in {t.name for t in tools}
        assert "exec" not in {t.name for t in tools}
