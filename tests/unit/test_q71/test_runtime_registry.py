"""Tests for RuntimeAgentRegistry — T477."""
from __future__ import annotations
from pathlib import Path
import pytest
from lidco.agents.factory import AgentConfig
from lidco.agents.runtime_registry import RuntimeAgentRegistry


def make_config(name="myagent"):
    return AgentConfig(name=name, description="desc", system_prompt="you are helpful", tools=["file_read"])


class TestRuntimeAgentRegistry:
    def test_register_and_get(self, tmp_path):
        reg = RuntimeAgentRegistry(project_dir=tmp_path)
        config = make_config("agent1")
        reg.register(config)
        assert reg.get("agent1") is not None

    def test_get_unknown(self, tmp_path):
        reg = RuntimeAgentRegistry(project_dir=tmp_path)
        assert reg.get("nope") is None

    def test_list_returns_registered(self, tmp_path):
        reg = RuntimeAgentRegistry(project_dir=tmp_path)
        reg.register(make_config("a"))
        reg.register(make_config("b"))
        names = [c.name for c in reg.list()]
        assert "a" in names
        assert "b" in names

    def test_unregister(self, tmp_path):
        reg = RuntimeAgentRegistry(project_dir=tmp_path)
        reg.register(make_config("todel"))
        reg.unregister("todel")
        assert reg.get("todel") is None

    def test_persists_to_yaml(self, tmp_path):
        reg = RuntimeAgentRegistry(project_dir=tmp_path)
        reg.register(make_config("persistent"))
        yaml_path = tmp_path / ".lidco" / "agents" / "persistent.yaml"
        assert yaml_path.exists()

    def test_hot_reload_from_disk(self, tmp_path):
        reg1 = RuntimeAgentRegistry(project_dir=tmp_path)
        reg1.register(make_config("loaded"))
        # New registry instance picks it up from disk
        reg2 = RuntimeAgentRegistry(project_dir=tmp_path)
        configs = reg2.list()
        names = [c.name for c in configs]
        assert "loaded" in names

    def test_unregister_missing(self, tmp_path):
        reg = RuntimeAgentRegistry(project_dir=tmp_path)
        assert not reg.unregister("nope")
