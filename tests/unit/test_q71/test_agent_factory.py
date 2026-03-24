"""Tests for AgentFactory — T476."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import patch
import pytest
from lidco.agents.factory import AgentConfig, AgentFactory, _slugify, _default_config


class TestAgentFactory:
    def test_synthesize_without_llm(self, tmp_path):
        factory = AgentFactory(project_dir=tmp_path)
        config = factory.synthesize("An agent that audits Python dependencies")
        assert isinstance(config, AgentConfig)
        assert config.name

    def test_name_is_slugified(self, tmp_path):
        factory = AgentFactory(project_dir=tmp_path)
        config = factory.synthesize("Audit Security Vulnerabilities!")
        assert " " not in config.name
        assert config.name == config.name.lower()

    def test_tools_validated_against_registry(self, tmp_path):
        factory = AgentFactory(project_dir=tmp_path)
        config = factory.synthesize("test agent")
        for tool in config.tools:
            assert tool in ("file_read", "file_write", "file_edit", "bash", "glob", "grep",
                            "git_status", "git_diff", "git_log", "web_search", "error_report")

    def test_writes_yaml_to_disk(self, tmp_path):
        factory = AgentFactory(project_dir=tmp_path)
        config = factory.synthesize("security scanner agent")
        yaml_files = list((tmp_path / ".lidco" / "agents").glob("*.yaml"))
        assert len(yaml_files) >= 1

    def test_llm_fn_used_when_provided(self, tmp_path):
        import json
        response = json.dumps({
            "name": "myagent",
            "system_prompt": "You are myagent",
            "tools": ["file_read", "bash"],
            "model": "claude-opus",
            "max_iterations": 100,
        })
        factory = AgentFactory(project_dir=tmp_path, llm_fn=lambda p: response)
        config = factory.synthesize("my agent description")
        assert config.name == "myagent"
        assert config.max_iterations == 100

    def test_llm_fn_exception_falls_back_to_default(self, tmp_path):
        def bad_llm(prompt):
            raise RuntimeError("LLM down")
        factory = AgentFactory(project_dir=tmp_path, llm_fn=bad_llm)
        config = factory.synthesize("some agent")
        assert config.name

    def test_default_config_has_tools(self, tmp_path):
        factory = AgentFactory(project_dir=tmp_path)
        config = factory.synthesize("test")
        assert len(config.tools) > 0

    def test_slugify(self):
        assert _slugify("Hello World!") == "hello_world"
        assert _slugify("") == "agent"
        assert " " not in _slugify("multi word description")
