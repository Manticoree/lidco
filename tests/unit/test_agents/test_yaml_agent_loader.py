"""Tests for YAML agent loader and discovery."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from lidco.agents.base import BaseAgent
from lidco.agents.loader import YAMLAgent, discover_yaml_agents, load_agent_from_yaml
from lidco.agents.registry import AgentRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_llm():
    return MagicMock()


@pytest.fixture()
def mock_registry():
    """ToolRegistry with a known set of tools."""
    registry = MagicMock()
    known = {"file_read", "glob", "grep"}

    def _get(name):
        return MagicMock() if name in known else None

    registry.get.side_effect = _get
    return registry


def _write_yaml(path: Path, data: dict) -> Path:
    path.write_text(yaml.dump(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# load_agent_from_yaml: valid inputs
# ---------------------------------------------------------------------------

class TestLoadAgentFromYaml:
    def test_load_full_yaml(self, tmp_path: Path, mock_llm, mock_registry) -> None:
        f = _write_yaml(tmp_path / "agent.yaml", {
            "name": "my-agent",
            "description": "Does cool things",
            "system_prompt": "You are an expert.",
            "model": "openai/glm-4.7",
            "temperature": 0.3,
            "tools": ["file_read", "glob"],
            "routing_keywords": ["deploy", "ship"],
        })

        agent = load_agent_from_yaml(f, mock_llm, mock_registry)

        assert agent.name == "my-agent"
        assert agent.description == "Does cool things"
        assert agent.config.system_prompt == "You are an expert."
        assert agent.config.model == "openai/glm-4.7"
        assert agent.config.temperature == 0.3
        assert agent.config.tools == ["file_read", "glob"]
        assert agent.config.routing_keywords == ["deploy", "ship"]

    def test_load_minimal_yaml(self, tmp_path: Path, mock_llm, mock_registry) -> None:
        f = _write_yaml(tmp_path / "min.yaml", {
            "name": "minimal",
            "system_prompt": "Be helpful.",
        })

        agent = load_agent_from_yaml(f, mock_llm, mock_registry)

        assert agent.name == "minimal"
        assert agent.config.description == ""
        assert agent.config.model is None
        assert agent.config.temperature == 0.1
        assert agent.config.tools == []
        assert agent.config.routing_keywords == []

    def test_returns_yaml_agent_instance(self, tmp_path: Path, mock_llm, mock_registry) -> None:
        f = _write_yaml(tmp_path / "a.yaml", {"name": "x", "system_prompt": "hi"})
        agent = load_agent_from_yaml(f, mock_llm, mock_registry)
        assert isinstance(agent, YAMLAgent)
        assert isinstance(agent, BaseAgent)

    def test_get_system_prompt(self, tmp_path: Path, mock_llm, mock_registry) -> None:
        f = _write_yaml(tmp_path / "a.yaml", {
            "name": "x",
            "system_prompt": "Custom system prompt here.",
        })
        agent = load_agent_from_yaml(f, mock_llm, mock_registry)
        assert agent.get_system_prompt() == "Custom system prompt here."

    def test_routing_keywords_stored(self, tmp_path: Path, mock_llm, mock_registry) -> None:
        f = _write_yaml(tmp_path / "a.yaml", {
            "name": "deployer",
            "system_prompt": "You deploy things.",
            "routing_keywords": ["deploy", "release", "ship"],
        })
        agent = load_agent_from_yaml(f, mock_llm, mock_registry)
        assert agent.config.routing_keywords == ["deploy", "release", "ship"]


# ---------------------------------------------------------------------------
# load_agent_from_yaml: validation errors
# ---------------------------------------------------------------------------

class TestLoadAgentValidation:
    def test_missing_name_raises(self, tmp_path: Path, mock_llm, mock_registry) -> None:
        f = _write_yaml(tmp_path / "bad.yaml", {"system_prompt": "hi"})
        with pytest.raises(ValueError, match="name"):
            load_agent_from_yaml(f, mock_llm, mock_registry)

    def test_missing_system_prompt_raises(self, tmp_path: Path, mock_llm, mock_registry) -> None:
        f = _write_yaml(tmp_path / "bad.yaml", {"name": "agent"})
        with pytest.raises(ValueError, match="system_prompt"):
            load_agent_from_yaml(f, mock_llm, mock_registry)

    def test_empty_name_raises(self, tmp_path: Path, mock_llm, mock_registry) -> None:
        f = _write_yaml(tmp_path / "bad.yaml", {"name": "", "system_prompt": "hi"})
        with pytest.raises(ValueError, match="name"):
            load_agent_from_yaml(f, mock_llm, mock_registry)

    def test_empty_file_raises(self, tmp_path: Path, mock_llm, mock_registry) -> None:
        f = tmp_path / "empty.yaml"
        f.write_text("", encoding="utf-8")
        with pytest.raises(ValueError):
            load_agent_from_yaml(f, mock_llm, mock_registry)


# ---------------------------------------------------------------------------
# load_agent_from_yaml: unknown tools warning
# ---------------------------------------------------------------------------

class TestUnknownToolWarning:
    def test_unknown_tool_emits_warning(
        self, tmp_path: Path, mock_llm, mock_registry, caplog: pytest.LogCaptureFixture
    ) -> None:
        f = _write_yaml(tmp_path / "a.yaml", {
            "name": "x",
            "system_prompt": "hi",
            "tools": ["file_read", "nonexistent_tool"],
        })
        import logging
        with caplog.at_level(logging.WARNING, logger="lidco.agents.loader"):
            agent = load_agent_from_yaml(f, mock_llm, mock_registry)

        assert agent is not None  # agent still created
        assert any("nonexistent_tool" in r.message for r in caplog.records)

    def test_known_tools_no_warning(
        self, tmp_path: Path, mock_llm, mock_registry, caplog: pytest.LogCaptureFixture
    ) -> None:
        f = _write_yaml(tmp_path / "a.yaml", {
            "name": "x",
            "system_prompt": "hi",
            "tools": ["file_read", "glob"],
        })
        import logging
        with caplog.at_level(logging.WARNING, logger="lidco.agents.loader"):
            load_agent_from_yaml(f, mock_llm, mock_registry)

        tool_warnings = [r for r in caplog.records if "unknown tool" in r.message.lower()]
        assert tool_warnings == []


# ---------------------------------------------------------------------------
# load_agent_from_yaml: backward-compat nested model format
# ---------------------------------------------------------------------------

class TestNestedModelBackwardCompat:
    def test_nested_model_format(
        self, tmp_path: Path, mock_llm, mock_registry, caplog: pytest.LogCaptureFixture
    ) -> None:
        f = _write_yaml(tmp_path / "legacy.yaml", {
            "name": "legacy",
            "system_prompt": "Legacy agent.",
            "model": {"preferred": "openai/glm-4.7", "temperature": 0.5, "fallback": "openai/glm-4.7"},
        })
        import logging
        with caplog.at_level(logging.WARNING, logger="lidco.agents.loader"):
            agent = load_agent_from_yaml(f, mock_llm, mock_registry)

        assert agent.config.model == "openai/glm-4.7"
        assert agent.config.temperature == 0.5
        assert agent.config.fallback_model == "openai/glm-4.7"
        assert any("deprecated" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# discover_yaml_agents
# ---------------------------------------------------------------------------

class TestDiscoverYamlAgents:
    def test_discovers_yaml_files(self, tmp_path: Path, mock_llm, mock_registry) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        _write_yaml(agents_dir / "a.yaml", {"name": "alpha", "system_prompt": "A"})
        _write_yaml(agents_dir / "b.yaml", {"name": "beta", "system_prompt": "B"})

        agents = discover_yaml_agents(mock_llm, mock_registry, search_dirs=[agents_dir])

        names = [a.name for a in agents]
        assert "alpha" in names
        assert "beta" in names

    def test_skips_invalid_yaml(
        self, tmp_path: Path, mock_llm, mock_registry, caplog: pytest.LogCaptureFixture
    ) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        _write_yaml(agents_dir / "valid.yaml", {"name": "ok", "system_prompt": "hi"})
        _write_yaml(agents_dir / "invalid.yaml", {"system_prompt": "no name"})

        import logging
        with caplog.at_level(logging.WARNING, logger="lidco.agents.loader"):
            agents = discover_yaml_agents(mock_llm, mock_registry, search_dirs=[agents_dir])

        assert len(agents) == 1
        assert agents[0].name == "ok"
        assert any("invalid.yaml" in r.message for r in caplog.records)

    def test_empty_directory_returns_empty(
        self, tmp_path: Path, mock_llm, mock_registry
    ) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        agents = discover_yaml_agents(mock_llm, mock_registry, search_dirs=[agents_dir])
        assert agents == []

    def test_nonexistent_directory_returns_empty(
        self, tmp_path: Path, mock_llm, mock_registry
    ) -> None:
        agents = discover_yaml_agents(
            mock_llm, mock_registry, search_dirs=[tmp_path / "no-such-dir"]
        )
        assert agents == []

    def test_returns_list_of_base_agents(
        self, tmp_path: Path, mock_llm, mock_registry
    ) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        _write_yaml(agents_dir / "x.yaml", {"name": "x", "system_prompt": "X"})

        agents = discover_yaml_agents(mock_llm, mock_registry, search_dirs=[agents_dir])
        assert all(isinstance(a, BaseAgent) for a in agents)


# ---------------------------------------------------------------------------
# Override built-in agent
# ---------------------------------------------------------------------------

class TestOverrideBuiltin:
    def test_yaml_agent_overrides_registry(
        self, tmp_path: Path, mock_llm, mock_registry
    ) -> None:
        registry = AgentRegistry()
        # Register a dummy built-in
        builtin = MagicMock(spec=BaseAgent)
        builtin.name = "coder"
        registry.register(builtin)

        # Load a YAML agent with the same name
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        _write_yaml(agents_dir / "coder.yaml", {
            "name": "coder",
            "system_prompt": "Custom coder.",
        })
        yaml_agents = discover_yaml_agents(mock_llm, mock_registry, search_dirs=[agents_dir])
        for agent in yaml_agents:
            registry.register(agent)

        # YAML agent should have replaced the built-in
        found = registry.get("coder")
        assert isinstance(found, YAMLAgent)


# ---------------------------------------------------------------------------
# Dynamic router prompt injection
# ---------------------------------------------------------------------------

class TestRouterPromptKeywords:
    def test_routing_keywords_appear_in_prompt(
        self, tmp_path: Path, mock_llm, mock_registry
    ) -> None:
        from lidco.agents.graph import GraphOrchestrator
        from lidco.agents.registry import AgentRegistry

        # Build a registry with one custom agent that has routing keywords
        reg = AgentRegistry()
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        _write_yaml(agents_dir / "deployer.yaml", {
            "name": "deployer",
            "description": "Deploys applications",
            "system_prompt": "You deploy.",
            "routing_keywords": ["deploy", "ship", "release"],
        })
        for agent in discover_yaml_agents(mock_llm, mock_registry, search_dirs=[agents_dir]):
            reg.register(agent)

        orchestrator = GraphOrchestrator(llm=mock_llm, agent_registry=reg)
        prompt = orchestrator._get_router_prompt()

        assert "deploy" in prompt
        assert "deployer" in prompt

    def test_no_keywords_no_custom_rules_line(
        self, tmp_path: Path, mock_llm, mock_registry
    ) -> None:
        from lidco.agents.graph import GraphOrchestrator
        from lidco.agents.registry import AgentRegistry

        reg = AgentRegistry()
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        _write_yaml(agents_dir / "plain.yaml", {
            "name": "plain",
            "system_prompt": "Plain agent.",
        })
        for agent in discover_yaml_agents(mock_llm, mock_registry, search_dirs=[agents_dir]):
            reg.register(agent)

        orchestrator = GraphOrchestrator(llm=mock_llm, agent_registry=reg)
        prompt = orchestrator._get_router_prompt()

        assert "Custom routing rules:" not in prompt
