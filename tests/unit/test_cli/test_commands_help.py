"""Tests for improved categorised /help command — Task 156."""

from __future__ import annotations

import asyncio

from lidco.cli.commands import CommandRegistry


def _run(coro) -> str:
    return asyncio.run(coro)


def _make_registry() -> CommandRegistry:
    return CommandRegistry()


# ── /help (no args) ───────────────────────────────────────────────────────────

class TestHelpNoArgs:
    def test_returns_string(self):
        reg = _make_registry()
        cmd = reg.get("help")
        result = _run(cmd.handler())
        assert isinstance(result, str)

    def test_contains_categories(self):
        reg = _make_registry()
        result = _run(reg.get("help").handler())
        assert "Агенты" in result
        assert "Сессия" in result
        assert "Отладка" in result

    def test_contains_key_commands(self):
        reg = _make_registry()
        result = _run(reg.get("help").handler())
        assert "/status" in result
        assert "/debug" in result
        assert "/lock" in result

    def test_has_tip_for_detailed_help(self):
        reg = _make_registry()
        result = _run(reg.get("help").handler())
        # Should mention /help <command>
        assert "help" in result.lower()

    def test_contains_agent_routing_syntax(self):
        reg = _make_registry()
        result = _run(reg.get("help").handler())
        assert "@" in result

    def test_contains_code_category(self):
        reg = _make_registry()
        result = _run(reg.get("help").handler())
        assert "lint" in result.lower() or "search" in result.lower()

    def test_contains_web_category(self):
        reg = _make_registry()
        result = _run(reg.get("help").handler())
        assert "websearch" in result.lower()

    def test_contains_export_import(self):
        reg = _make_registry()
        result = _run(reg.get("help").handler())
        assert "export" in result.lower() or "import" in result.lower()

    def test_markdown_formatted(self):
        reg = _make_registry()
        result = _run(reg.get("help").handler())
        assert "**" in result or "##" in result


# ── /help <command> ───────────────────────────────────────────────────────────

class TestHelpWithArg:
    def test_known_command_returns_description(self):
        reg = _make_registry()
        result = _run(reg.get("help").handler(arg="debug"))
        assert "debug" in result.lower()

    def test_known_command_with_examples(self):
        reg = _make_registry()
        result = _run(reg.get("help").handler(arg="debug"))
        # Should show examples since debug is in _HELP_EXAMPLES
        assert "Пример" in result or "/debug" in result

    def test_unknown_command_returns_error_message(self):
        reg = _make_registry()
        result = _run(reg.get("help").handler(arg="nonexistent_xyz"))
        assert "не найден" in result or "not found" in result.lower()

    def test_with_slash_prefix(self):
        reg = _make_registry()
        result = _run(reg.get("help").handler(arg="/status"))
        assert "status" in result.lower()

    def test_as_command_detail(self):
        reg = _make_registry()
        result = _run(reg.get("help").handler(arg="as"))
        assert "as" in result.lower()

    def test_lock_command_detail(self):
        reg = _make_registry()
        result = _run(reg.get("help").handler(arg="lock"))
        assert "lock" in result.lower()

    def test_export_command_detail(self):
        reg = _make_registry()
        result = _run(reg.get("help").handler(arg="export"))
        assert "export" in result.lower()
