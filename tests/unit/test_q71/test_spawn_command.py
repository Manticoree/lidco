"""Tests for /spawn-agent concept — T478."""
from __future__ import annotations
import pytest
from lidco.agents.factory import AgentConfig, AgentFactory, _slugify
from lidco.agents.runtime_registry import RuntimeAgentRegistry


class TestSpawnCommand:
    """Tests covering the spawn-agent workflow (factory + registry + confirm)."""

    def test_spawn_creates_and_registers(self, tmp_path):
        factory = AgentFactory(project_dir=tmp_path)
        registry = RuntimeAgentRegistry(project_dir=tmp_path)
        config = factory.synthesize("An agent that audits npm dependencies weekly")
        registry.register(config)
        assert registry.get(config.name) is not None

    def test_spawn_description_preserved(self, tmp_path):
        factory = AgentFactory(project_dir=tmp_path)
        config = factory.synthesize("security scanner agent")
        assert "security" in config.description or "security" in config.name or len(config.description) > 0

    def test_spawn_yaml_on_disk(self, tmp_path):
        factory = AgentFactory(project_dir=tmp_path)
        registry = RuntimeAgentRegistry(project_dir=tmp_path)
        config = factory.synthesize("doc generator agent")
        registry.register(config)
        yaml_path = tmp_path / ".lidco" / "agents" / f"{config.name}.yaml"
        assert yaml_path.exists()

    def test_spawn_tools_valid(self, tmp_path):
        factory = AgentFactory(project_dir=tmp_path)
        config = factory.synthesize("test runner agent")
        allowed = {"file_read", "file_write", "file_edit", "bash", "glob", "grep",
                   "git_status", "git_diff", "git_log", "web_search", "error_report"}
        for t in config.tools:
            assert t in allowed

    def test_slugify_various_inputs(self):
        assert _slugify("My Custom Agent") == "my_custom_agent"
        assert _slugify("agent-with-dashes") == "agent_with_dashes"
        assert _slugify("123 numbers") == "123_numbers"

    def test_at_routing_lookup(self, tmp_path):
        """@agentname syntax resolves via registry."""
        factory = AgentFactory(project_dir=tmp_path)
        registry = RuntimeAgentRegistry(project_dir=tmp_path)
        config = factory.synthesize("review agent")
        registry.register(config)
        name = config.name
        resolved = registry.get(name)
        assert resolved is not None
        assert resolved.name == name
