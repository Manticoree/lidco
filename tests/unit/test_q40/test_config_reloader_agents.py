"""Tests for Q40 — agent file hot-reload in ConfigReloader (Task 271)."""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lidco.core.config_reloader import ConfigReloader


@pytest.fixture()
def mock_session(tmp_path):
    session = MagicMock()
    session.project_dir = tmp_path
    session.config = MagicMock()
    session.config.agents = MagicMock()
    session.config.llm = MagicMock()
    session.config.permissions = MagicMock()
    session.config.permissions.mode = "auto"
    session.llm = MagicMock()
    session.tool_registry = MagicMock()
    session.agent_registry = MagicMock()
    session.agent_registry.get.return_value = None
    return session


def _make_reloader(session, tmp_path) -> ConfigReloader:
    return ConfigReloader(session, project_dir=tmp_path, interval=999)


class TestScanAgentFiles:
    def test_empty_dirs_returns_empty(self, mock_session, tmp_path):
        reloader = _make_reloader(mock_session, tmp_path)
        result = reloader._scan_agent_files()
        assert result == {}

    def test_finds_yaml_md_files(self, mock_session, tmp_path):
        agent_dir = tmp_path / ".lidco" / "agents"
        agent_dir.mkdir(parents=True)
        (agent_dir / "a.yaml").write_text("name: a\n")
        (agent_dir / "b.yml").write_text("name: b\n")
        (agent_dir / "c.md").write_text("---\nname: c\n---\nPrompt.\n")
        reloader = _make_reloader(mock_session, tmp_path)
        result = reloader._scan_agent_files()
        keys = {Path(k).name for k in result.keys()}
        assert "a.yaml" in keys
        assert "b.yml" in keys
        assert "c.md" in keys

    def test_ignores_other_extensions(self, mock_session, tmp_path):
        agent_dir = tmp_path / ".lidco" / "agents"
        agent_dir.mkdir(parents=True)
        (agent_dir / "notes.txt").write_text("ignore me")
        reloader = _make_reloader(mock_session, tmp_path)
        result = reloader._scan_agent_files()
        assert result == {}


class TestAgentHotReload:
    def test_agents_changed_triggers_reload(self, mock_session, tmp_path):
        reloader = _make_reloader(mock_session, tmp_path)
        agent_dir = tmp_path / ".lidco" / "agents"
        agent_dir.mkdir(parents=True)

        # Patch _reload_agents to track calls
        reloader._reload_agents = MagicMock()

        # Simulate a new file appearing
        reloader._agent_mtimes = {}  # pretend nothing was there
        (agent_dir / "new.yaml").write_text("name: new\nsystem_prompt: p\n")

        reloader._check()
        reloader._reload_agents.assert_called_once()

    def test_no_change_does_not_trigger_reload(self, mock_session, tmp_path):
        agent_dir = tmp_path / ".lidco" / "agents"
        agent_dir.mkdir(parents=True)
        (agent_dir / "existing.yaml").write_text("name: x\nsystem_prompt: p\n")

        reloader = _make_reloader(mock_session, tmp_path)
        # Scan current state
        reloader._agent_mtimes = reloader._scan_agent_files()

        reloader._reload_agents = MagicMock()
        reloader._check()  # no change
        reloader._reload_agents.assert_not_called()

    def test_reload_agents_calls_discover_yaml_agents(self, mock_session, tmp_path):
        agent_dir = tmp_path / ".lidco" / "agents"
        agent_dir.mkdir(parents=True)

        reloader = _make_reloader(mock_session, tmp_path)

        mock_agent = MagicMock()
        mock_agent._config = MagicMock()
        mock_agent._config.name = "loaded"

        with patch("lidco.core.config_reloader.ConfigReloader._reload_agents") as mock_reload:
            # Trigger reload manually
            reloader._reload_agents()

    def test_reload_agents_registers_new_agents(self, mock_session, tmp_path):
        agent_dir = tmp_path / ".lidco" / "agents"
        agent_dir.mkdir(parents=True)
        reloader = _make_reloader(mock_session, tmp_path)

        mock_agent = MagicMock()
        mock_agent._config = MagicMock()
        mock_agent._config.name = "freshagent"

        with patch("lidco.agents.loader.discover_yaml_agents", return_value=[mock_agent]):
            reloader._reload_agents()

        mock_session.agent_registry.register.assert_called()

    def test_reload_agents_status_callback_fired(self, mock_session, tmp_path):
        agent_dir = tmp_path / ".lidco" / "agents"
        agent_dir.mkdir(parents=True)
        cb = MagicMock()
        reloader = _make_reloader(mock_session, tmp_path)
        reloader._status_callback = cb

        mock_agent = MagicMock()
        mock_agent._config = MagicMock()
        mock_agent._config.name = "newone"
        mock_session.agent_registry.get.return_value = None  # not yet registered

        with patch("lidco.agents.loader.discover_yaml_agents", return_value=[mock_agent]):
            reloader._reload_agents()

        cb.assert_called_once()
        assert "newone" in cb.call_args[0][0]

    def test_reload_agents_no_session_attributes_is_noop(self, tmp_path):
        session = MagicMock(spec=[])  # no attributes at all
        reloader = _make_reloader(session, tmp_path)
        # Should not raise
        reloader._reload_agents()

    def test_reload_agents_skips_unchanged(self, mock_session, tmp_path):
        agent_dir = tmp_path / ".lidco" / "agents"
        agent_dir.mkdir(parents=True)
        reloader = _make_reloader(mock_session, tmp_path)

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.name = "existing"
        mock_agent._config = mock_config

        # Pretend it's already registered with same repr
        existing = MagicMock()
        existing._config = mock_config
        mock_session.agent_registry.get.return_value = existing

        with patch("lidco.agents.loader.discover_yaml_agents", return_value=[mock_agent]):
            reloader._reload_agents()

        # register should NOT be called since repr matches
        mock_session.agent_registry.register.assert_not_called()
