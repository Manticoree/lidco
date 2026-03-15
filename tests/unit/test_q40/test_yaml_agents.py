"""Tests for Q40 — YAML/Markdown agent loading (Tasks 268-271, 273-274)."""
from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lidco.agents.loader import _parse_md_agent, load_agent_from_yaml, discover_yaml_agents
from lidco.agents.base import AgentConfig


# ── _parse_md_agent ───────────────────────────────────────────────────────────

class TestParseMdAgent:
    def test_basic_frontmatter(self):
        text = textwrap.dedent("""\
            ---
            name: my-agent
            description: A test agent
            ---
            You are a helpful assistant.
        """)
        data = _parse_md_agent(text)
        assert data["name"] == "my-agent"
        assert data["description"] == "A test agent"
        assert data["system_prompt"] == "You are a helpful assistant."

    def test_body_overrides_frontmatter_prompt(self):
        text = textwrap.dedent("""\
            ---
            name: agent
            system_prompt: old prompt
            ---
            New prompt from body.
        """)
        data = _parse_md_agent(text)
        assert data["system_prompt"] == "New prompt from body."

    def test_no_body_keeps_frontmatter_prompt(self):
        text = textwrap.dedent("""\
            ---
            name: agent
            system_prompt: keep this
            ---
        """)
        data = _parse_md_agent(text)
        assert data["system_prompt"] == "keep this"

    def test_missing_frontmatter_raises(self):
        with pytest.raises(ValueError, match="No YAML frontmatter"):
            _parse_md_agent("just plain text without delimiters")

    def test_all_q40_fields_parsed(self):
        text = textwrap.dedent("""\
            ---
            name: secure
            disallowed_tools:
              - bash
              - file_write
            permission_mode: ask
            memory: agent
            isolation: worktree
            hooks:
              post_response: echo done
            max_turns: 10
            ---
            Security reviewer agent.
        """)
        data = _parse_md_agent(text)
        assert data["disallowed_tools"] == ["bash", "file_write"]
        assert data["permission_mode"] == "ask"
        assert data["memory"] == "agent"
        assert data["isolation"] == "worktree"
        assert data["hooks"] == {"post_response": "echo done"}
        assert data["max_turns"] == 10

    def test_routing_keywords_parsed(self):
        text = textwrap.dedent("""\
            ---
            name: router
            routing_keywords: [security, audit, vuln]
            ---
            Route me.
        """)
        data = _parse_md_agent(text)
        assert data["routing_keywords"] == ["security", "audit", "vuln"]


# ── load_agent_from_yaml ──────────────────────────────────────────────────────

@pytest.fixture()
def mock_llm():
    return MagicMock()


@pytest.fixture()
def mock_registry():
    r = MagicMock()
    r.get.return_value = None
    return r


def _write_agent_file(tmp_path: Path, filename: str, content: str) -> Path:
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


class TestLoadAgentFromYaml:
    def test_yaml_basic(self, tmp_path, mock_llm, mock_registry):
        p = _write_agent_file(tmp_path, "agent.yaml", textwrap.dedent("""\
            name: basic
            system_prompt: You are basic.
            description: Basic agent
        """))
        agent = load_agent_from_yaml(p, mock_llm, mock_registry)
        assert agent._config.name == "basic"
        assert agent._config.system_prompt == "You are basic."
        assert agent._config.description == "Basic agent"

    def test_md_frontmatter(self, tmp_path, mock_llm, mock_registry):
        p = _write_agent_file(tmp_path, "agent.md", textwrap.dedent("""\
            ---
            name: md-agent
            description: MD agent
            ---
            System prompt from body.
        """))
        agent = load_agent_from_yaml(p, mock_llm, mock_registry)
        assert agent._config.name == "md-agent"
        assert agent._config.system_prompt == "System prompt from body."

    def test_disallowed_tools_loaded(self, tmp_path, mock_llm, mock_registry):
        p = _write_agent_file(tmp_path, "agent.yaml", textwrap.dedent("""\
            name: restricted
            system_prompt: Prompt.
            disallowed_tools:
              - bash
              - file_delete
        """))
        agent = load_agent_from_yaml(p, mock_llm, mock_registry)
        assert agent._config.disallowed_tools == ["bash", "file_delete"]

    def test_permission_mode_loaded(self, tmp_path, mock_llm, mock_registry):
        p = _write_agent_file(tmp_path, "agent.yaml", textwrap.dedent("""\
            name: careful
            system_prompt: Prompt.
            permission_mode: ask
        """))
        agent = load_agent_from_yaml(p, mock_llm, mock_registry)
        assert agent._config.permission_mode == "ask"

    def test_memory_field_loaded(self, tmp_path, mock_llm, mock_registry):
        p = _write_agent_file(tmp_path, "agent.yaml", textwrap.dedent("""\
            name: memtest
            system_prompt: Prompt.
            memory: agent
        """))
        agent = load_agent_from_yaml(p, mock_llm, mock_registry)
        assert agent._config.memory == "agent"

    def test_isolation_field_loaded(self, tmp_path, mock_llm, mock_registry):
        p = _write_agent_file(tmp_path, "agent.yaml", textwrap.dedent("""\
            name: isolated
            system_prompt: Prompt.
            isolation: worktree
        """))
        agent = load_agent_from_yaml(p, mock_llm, mock_registry)
        assert agent._config.isolation == "worktree"

    def test_hooks_loaded(self, tmp_path, mock_llm, mock_registry):
        p = _write_agent_file(tmp_path, "agent.yaml", textwrap.dedent("""\
            name: hooked
            system_prompt: Prompt.
            hooks:
              post_response: echo done
        """))
        agent = load_agent_from_yaml(p, mock_llm, mock_registry)
        assert agent._config.hooks == {"post_response": "echo done"}

    def test_max_turns_maps_to_max_iterations(self, tmp_path, mock_llm, mock_registry):
        p = _write_agent_file(tmp_path, "agent.yaml", textwrap.dedent("""\
            name: limited
            system_prompt: Prompt.
            max_turns: 5
        """))
        agent = load_agent_from_yaml(p, mock_llm, mock_registry)
        assert agent._config.max_iterations == 5

    def test_missing_name_raises(self, tmp_path, mock_llm, mock_registry):
        p = _write_agent_file(tmp_path, "agent.yaml", "system_prompt: ok\n")
        with pytest.raises(ValueError, match="missing required field"):
            load_agent_from_yaml(p, mock_llm, mock_registry)

    def test_missing_prompt_raises(self, tmp_path, mock_llm, mock_registry):
        p = _write_agent_file(tmp_path, "agent.yaml", "name: noPrompt\n")
        with pytest.raises(ValueError, match="missing required field"):
            load_agent_from_yaml(p, mock_llm, mock_registry)

    def test_default_fields(self, tmp_path, mock_llm, mock_registry):
        p = _write_agent_file(tmp_path, "agent.yaml", textwrap.dedent("""\
            name: defaults
            system_prompt: Prompt.
        """))
        agent = load_agent_from_yaml(p, mock_llm, mock_registry)
        cfg = agent._config
        assert cfg.disallowed_tools == []
        assert cfg.permission_mode is None
        assert cfg.memory == "project"
        assert cfg.isolation == "none"
        assert cfg.hooks == {}
        assert cfg.max_iterations == 200


class TestDiscoverYamlAgents:
    def test_discovers_yaml_and_md(self, tmp_path, mock_llm, mock_registry):
        _write_agent_file(tmp_path, "a.yaml", "name: agt1\nsystem_prompt: p1\n")
        _write_agent_file(tmp_path, "b.md", textwrap.dedent("""\
            ---
            name: agt2
            ---
            Prompt two.
        """))
        agents = discover_yaml_agents(mock_llm, mock_registry, search_dirs=[tmp_path])
        names = {a._config.name for a in agents}
        assert "agt1" in names
        assert "agt2" in names

    def test_invalid_files_skipped(self, tmp_path, mock_llm, mock_registry):
        _write_agent_file(tmp_path, "good.yaml", "name: good\nsystem_prompt: ok\n")
        _write_agent_file(tmp_path, "bad.yaml", "not: valid: yaml: content: ---\n")
        agents = discover_yaml_agents(mock_llm, mock_registry, search_dirs=[tmp_path])
        # good agent is loaded; bad one is silently skipped
        assert any(a._config.name == "good" for a in agents)

    def test_nonexistent_dir_ignored(self, tmp_path, mock_llm, mock_registry):
        agents = discover_yaml_agents(
            mock_llm, mock_registry, search_dirs=[tmp_path / "does_not_exist"]
        )
        assert agents == []


# ── AgentConfig new fields ───────────────────────────────────────────────────

class TestAgentConfigNewFields:
    def test_fields_exist_with_defaults(self):
        cfg = AgentConfig(name="x", description="d", system_prompt="p")
        assert hasattr(cfg, "disallowed_tools")
        assert hasattr(cfg, "permission_mode")
        assert hasattr(cfg, "memory")
        assert hasattr(cfg, "isolation")
        assert hasattr(cfg, "hooks")
        assert cfg.disallowed_tools == []
        assert cfg.permission_mode is None
        assert cfg.memory == "project"
        assert cfg.isolation == "none"
        assert cfg.hooks == {}

    def test_fields_settable(self):
        cfg = AgentConfig(
            name="x", description="d", system_prompt="p",
            disallowed_tools=["bash"],
            permission_mode="ask",
            memory="none",
            isolation="worktree",
            hooks={"post_response": "echo"},
        )
        assert cfg.disallowed_tools == ["bash"]
        assert cfg.permission_mode == "ask"
        assert cfg.memory == "none"
        assert cfg.isolation == "worktree"
        assert cfg.hooks == {"post_response": "echo"}
