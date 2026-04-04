"""Tests for Q305 CLI commands."""

import asyncio
from unittest.mock import patch, MagicMock

import pytest

from lidco.githooks.manager import HookType, HookResult


class TestGitHooksCmd:
    def _run(self, args: str) -> str:
        from lidco.cli.commands.q305_cmds import register_q305_commands
        registry = MagicMock()
        register_q305_commands(registry)
        # git-hooks is the first registered command
        handler = registry.register.call_args_list[0][0][0].handler
        return asyncio.run(handler(args))

    def test_no_args_shows_usage(self):
        result = self._run("")
        assert "Usage" in result

    @patch("lidco.githooks.manager.HookManagerV2.list_installed", return_value=[])
    def test_list_empty(self, _mock):
        result = self._run("list")
        assert "No hooks installed" in result

    @patch("lidco.githooks.manager.HookManagerV2.list_installed", return_value=[HookType.PRE_COMMIT])
    def test_list_with_hooks(self, _mock):
        result = self._run("list")
        assert "pre-commit" in result

    def test_install_missing_args(self):
        result = self._run("install pre-commit")
        assert "Error" in result

    def test_install_bad_type(self):
        result = self._run("install bad-type script")
        assert "Error" in result

    @patch("lidco.githooks.manager.HookManagerV2.uninstall", return_value=True)
    def test_uninstall_success(self, _mock):
        result = self._run("uninstall pre-commit")
        assert "removed" in result.lower()

    @patch("lidco.githooks.manager.HookManagerV2.uninstall", return_value=False)
    def test_uninstall_not_installed(self, _mock):
        result = self._run("uninstall pre-commit")
        assert "not installed" in result.lower()

    def test_unknown_subcommand(self):
        result = self._run("foobar")
        assert "Unknown" in result


class TestHookLibraryCmd:
    def _run(self, args: str) -> str:
        from lidco.cli.commands.q305_cmds import register_q305_commands
        registry = MagicMock()
        register_q305_commands(registry)
        handler = registry.register.call_args_list[1][0][0].handler
        return asyncio.run(handler(args))

    def test_list_default(self):
        result = self._run("")
        assert "Hook Library" in result

    def test_categories(self):
        result = self._run("categories")
        assert "Categories" in result

    def test_get_existing(self):
        result = self._run("get no-debug")
        assert "no-debug" in result

    def test_get_missing(self):
        result = self._run("get nonexistent")
        assert "not found" in result.lower()

    def test_lang_python(self):
        result = self._run("lang python")
        assert "python" in result.lower()


class TestHookStatsCmd:
    def _run(self, args: str) -> str:
        from lidco.cli.commands.q305_cmds import register_q305_commands
        registry = MagicMock()
        register_q305_commands(registry)
        handler = registry.register.call_args_list[3][0][0].handler
        return asyncio.run(handler(args))

    def test_summary_default(self):
        result = self._run("")
        assert "Total runs" in result

    def test_pass_rate(self):
        result = self._run("pass-rate lint")
        assert "Pass rate" in result

    def test_failures(self):
        result = self._run("failures")
        assert "No failures" in result or "Most failed" in result
