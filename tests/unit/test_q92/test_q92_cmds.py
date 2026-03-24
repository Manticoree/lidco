"""Tests for src/lidco/cli/commands/q92_cmds.py."""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from lidco.cli.commands.q92_cmds import register_q92_commands


def make_registry():
    registry = MagicMock()
    registry._commands = {}
    registry._last_messages = []

    def _register(cmd):
        registry._commands[cmd.name] = cmd

    registry.register.side_effect = _register
    return registry


def get_handler(registry, name):
    return registry._commands[name].handler


class TestRegistration:
    def test_all_commands_registered(self):
        registry = make_registry()
        register_q92_commands(registry)
        assert "prompt" in registry._commands
        assert "export" in registry._commands
        assert "team" in registry._commands
        assert "hot-reload" in registry._commands

    def test_register_called_four_times(self):
        registry = make_registry()
        register_q92_commands(registry)
        assert registry.register.call_count == 4


class TestPromptCommand:
    def test_list_empty(self, tmp_path):
        registry = make_registry()
        register_q92_commands(registry)
        handler = get_handler(registry, "prompt")
        with patch("lidco.prompts.library.PromptTemplateLibrary") as MockLib:
            MockLib.return_value.list.return_value = []
            result = handler("list")
        assert "No prompt templates" in result

    def test_list_with_templates(self, tmp_path):
        from lidco.prompts.library import PromptTemplate

        registry = make_registry()
        register_q92_commands(registry)
        handler = get_handler(registry, "prompt")
        tpl = PromptTemplate(name="fix", content="", variables=["lang"], source_path="fix.md")
        with patch("lidco.prompts.library.PromptTemplateLibrary") as MockLib:
            MockLib.return_value.list.return_value = [tpl]
            result = handler("list")
        assert "fix" in result

    def test_run_missing_name(self):
        registry = make_registry()
        register_q92_commands(registry)
        handler = get_handler(registry, "prompt")
        result = handler("run")
        assert "Usage" in result

    def test_run_template_not_found(self):
        from lidco.prompts.library import RenderResult

        registry = make_registry()
        register_q92_commands(registry)
        handler = get_handler(registry, "prompt")
        with patch("lidco.prompts.library.PromptTemplateLibrary") as MockLib:
            # B6: not-found is indicated by found=False, not by empty rendered
            MockLib.return_value.render.return_value = RenderResult(
                name="missing", rendered="", found=False
            )
            result = handler("run missing")
        assert "not found" in result

    def test_run_with_variables(self):
        from lidco.prompts.library import RenderResult

        registry = make_registry()
        register_q92_commands(registry)
        handler = get_handler(registry, "prompt")
        with patch("lidco.prompts.library.PromptTemplateLibrary") as MockLib:
            MockLib.return_value.render.return_value = RenderResult(
                name="greet", rendered="Hello Alice!"
            )
            result = handler("run greet name=Alice")
        assert "Hello Alice!" in result

    def test_save_missing_content(self):
        registry = make_registry()
        register_q92_commands(registry)
        handler = get_handler(registry, "prompt")
        result = handler("save myname")
        assert "Usage" in result

    def test_save_success(self):
        from lidco.prompts.library import PromptTemplate

        registry = make_registry()
        register_q92_commands(registry)
        handler = get_handler(registry, "prompt")
        tpl = PromptTemplate(name="new", content="content", variables=[], source_path="/p/new.md")
        with patch("lidco.prompts.library.PromptTemplateLibrary") as MockLib:
            MockLib.return_value.save.return_value = tpl
            result = handler("save new content here")
        assert "new" in result

    def test_unknown_subcmd(self):
        registry = make_registry()
        register_q92_commands(registry)
        handler = get_handler(registry, "prompt")
        result = handler("unknown")
        assert "Usage" in result


class TestExportCommand:
    def test_no_messages(self):
        registry = make_registry()
        registry._last_messages = []
        register_q92_commands(registry)
        handler = get_handler(registry, "export")
        result = handler("")
        assert "No conversation" in result

    def test_markdown_export(self):
        from lidco.export.session_exporter import ExportResult

        registry = make_registry()
        registry._last_messages = [{"role": "user", "content": "hi"}]
        register_q92_commands(registry)
        handler = get_handler(registry, "export")
        with patch("lidco.export.session_exporter.SessionExporter") as MockExp:
            MockExp.return_value.export.return_value = ExportResult(
                content="## User\nhi\n", format="markdown", message_count=1
            )
            result = handler("md")
        assert "## User" in result

    def test_html_format_selected(self):
        from lidco.export.session_exporter import ExportResult

        registry = make_registry()
        registry._last_messages = [{"role": "user", "content": "hi"}]
        register_q92_commands(registry)
        handler = get_handler(registry, "export")
        with patch("lidco.export.session_exporter.SessionExporter") as MockExp:
            mock_exp = MockExp.return_value
            mock_exp.export.return_value = ExportResult(
                content="<html/>", format="html", message_count=1
            )
            handler("html")
            call_args = mock_exp.export.call_args
            config = call_args[0][1]
            assert config.format == "html"


class TestTeamCommand:
    def test_show_no_config(self):
        registry = make_registry()
        register_q92_commands(registry)
        handler = get_handler(registry, "team")
        with patch("lidco.config.team_config.TeamConfigLoader") as MockLoader:
            from lidco.config.team_config import MergedConfig, TeamConfig

            MockLoader.return_value.load.return_value = MergedConfig(
                team=TeamConfig(), personal={}, resolved={"model": "", "tools": [], "rules": [], "members": [], "permissions": {}}
            )
            result = handler("show")
        assert "model" in result.lower() or "configuration" in result.lower()

    def test_validate_no_file(self):
        registry = make_registry()
        register_q92_commands(registry)
        handler = get_handler(registry, "team")
        with patch("lidco.config.team_config.TeamConfigLoader") as MockLoader:
            MockLoader.return_value.load_team.return_value = None
            result = handler("validate")
        assert "No" in result

    def test_validate_valid(self):
        from lidco.config.team_config import TeamConfig

        registry = make_registry()
        register_q92_commands(registry)
        handler = get_handler(registry, "team")
        with patch("lidco.config.team_config.TeamConfigLoader") as MockLoader:
            MockLoader.return_value.load_team.return_value = TeamConfig()
            MockLoader.return_value.validate.return_value = []
            result = handler("validate")
        assert "valid" in result.lower()

    def test_unknown_subcmd(self):
        registry = make_registry()
        register_q92_commands(registry)
        handler = get_handler(registry, "team")
        result = handler("unknown")
        assert "Usage" in result


class TestHotReloadCommand:
    def test_successful_reload(self):
        registry = make_registry()
        register_q92_commands(registry)
        handler = get_handler(registry, "hot-reload")
        mock_config = MagicMock()
        mock_config.model = "claude-sonnet-4-6"
        with patch("lidco.core.config.load_config", return_value=mock_config):
            result = handler("")
        assert "reloaded" in result.lower()

    def test_reload_failure(self):
        registry = make_registry()
        register_q92_commands(registry)
        handler = get_handler(registry, "hot-reload")
        with patch("lidco.core.config.load_config", side_effect=RuntimeError("boom")):
            result = handler("")
        assert "failed" in result.lower() or "boom" in result
