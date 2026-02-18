"""Tests for agent registry and loader."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from lidco.agents.base import AgentConfig, BaseAgent, AgentResponse
from lidco.agents.registry import AgentRegistry
from lidco.agents.loader import load_agent_from_yaml, discover_yaml_agents


class MockAgent(BaseAgent):
    def get_system_prompt(self) -> str:
        return self._config.system_prompt


def make_mock_agent(name: str = "test") -> BaseAgent:
    config = AgentConfig(
        name=name,
        description=f"{name} agent",
        system_prompt="You are a test agent.",
    )
    llm = MagicMock()
    registry = MagicMock()
    return MockAgent(config=config, llm=llm, tool_registry=registry)


class TestAgentRegistry:
    def test_register_and_get(self):
        registry = AgentRegistry()
        agent = make_mock_agent("coder")
        registry.register(agent)
        assert registry.get("coder") is agent

    def test_get_nonexistent(self):
        registry = AgentRegistry()
        assert registry.get("nonexistent") is None

    def test_list_agents(self):
        registry = AgentRegistry()
        registry.register(make_mock_agent("a"))
        registry.register(make_mock_agent("b"))
        assert len(registry.list_agents()) == 2

    def test_list_names(self):
        registry = AgentRegistry()
        registry.register(make_mock_agent("x"))
        registry.register(make_mock_agent("y"))
        assert set(registry.list_names()) == {"x", "y"}

    def test_overwrite_agent(self):
        registry = AgentRegistry()
        agent1 = make_mock_agent("same")
        agent2 = make_mock_agent("same")
        registry.register(agent1)
        registry.register(agent2)
        assert registry.get("same") is agent2
        assert len(registry.list_agents()) == 1


class TestYAMLLoader:
    def test_load_agent_from_yaml(self, tmp_path):
        yaml_content = """
name: test-agent
description: "A test agent"
model:
  preferred: gpt-4o
  temperature: 0.3
system_prompt: "You are a test."
tools:
  - file_read
  - grep
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        llm = MagicMock()
        tool_reg = MagicMock()
        agent = load_agent_from_yaml(yaml_file, llm, tool_reg)

        assert agent.name == "test-agent"
        assert agent.description == "A test agent"
        assert agent.config.model == "gpt-4o"
        assert agent.config.temperature == 0.3
        assert agent.config.tools == ["file_read", "grep"]

    def test_discover_yaml_agents(self, tmp_path):
        for name in ["agent1", "agent2"]:
            (tmp_path / f"{name}.yaml").write_text(
                f"name: {name}\ndescription: test\nsystem_prompt: test\n"
            )

        llm = MagicMock()
        tool_reg = MagicMock()
        agents = discover_yaml_agents(llm, tool_reg, search_dirs=[tmp_path])
        assert len(agents) == 2

    def test_discover_empty_dir(self, tmp_path):
        llm = MagicMock()
        tool_reg = MagicMock()
        agents = discover_yaml_agents(llm, tool_reg, search_dirs=[tmp_path])
        assert len(agents) == 0

    def test_discover_invalid_yaml_skipped(self, tmp_path):
        (tmp_path / "bad.yaml").write_text("not: valid: yaml: [")
        llm = MagicMock()
        tool_reg = MagicMock()
        agents = discover_yaml_agents(llm, tool_reg, search_dirs=[tmp_path])
        assert len(agents) == 0
