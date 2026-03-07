"""Tests for /note (#167), enhanced completer (#168), /alias (#169)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from prompt_toolkit.document import Document

from lidco.cli.commands import CommandRegistry
from lidco.cli.completer import LidcoCompleter


def _run(coro) -> str:
    return asyncio.run(coro)


def _make_registry() -> CommandRegistry:
    return CommandRegistry()


# ── Task 167: /note ───────────────────────────────────────────────────────────

class TestNoteCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("note") is not None

    def test_default_note_empty(self):
        reg = _make_registry()
        assert reg.session_note == ""

    def test_set_note(self):
        reg = _make_registry()
        _run(reg.get("note").handler(arg="always use Python 3.13"))
        assert reg.session_note == "always use Python 3.13"

    def test_set_returns_confirmation(self):
        reg = _make_registry()
        result = _run(reg.get("note").handler(arg="focus on async"))
        assert "focus on async" in result

    def test_show_current_note(self):
        reg = _make_registry()
        reg.session_note = "use asyncio everywhere"
        result = _run(reg.get("note").handler(arg=""))
        assert "use asyncio everywhere" in result

    def test_show_empty_note(self):
        reg = _make_registry()
        result = _run(reg.get("note").handler(arg=""))
        assert "не установлена" in result or "not set" in result.lower()

    def test_clear_note(self):
        reg = _make_registry()
        reg.session_note = "something"
        _run(reg.get("note").handler(arg="clear"))
        assert reg.session_note == ""

    def test_clear_returns_message(self):
        reg = _make_registry()
        reg.session_note = "something"
        result = _run(reg.get("note").handler(arg="clear"))
        assert "очищена" in result or "cleared" in result.lower()

    def test_overwrite_note(self):
        reg = _make_registry()
        _run(reg.get("note").handler(arg="note v1"))
        _run(reg.get("note").handler(arg="note v2"))
        assert reg.session_note == "note v2"

    def test_note_persists_between_calls(self):
        reg = _make_registry()
        _run(reg.get("note").handler(arg="persistent note"))
        result = _run(reg.get("note").handler(arg=""))
        assert "persistent note" in result


# ── Task 168: enhanced completer ──────────────────────────────────────────────

class TestEnhancedCompleter:
    def _completer(self, agents=None, commands=None) -> LidcoCompleter:
        return LidcoCompleter(
            agent_names=agents or ["coder", "tester", "debugger", "architect"],
            command_meta={c: "cmd" for c in (commands or ["as", "whois", "lock", "help", "clear", "status"])},
        )

    def _complete(self, completer: LidcoCompleter, text: str) -> list[str]:
        doc = Document(text, cursor_position=len(text))
        return [c.text for c in completer.get_completions(doc, None)]

    def test_as_completes_agents(self):
        c = self._completer()
        results = self._complete(c, "/as ")
        assert "coder " in results or "coder" in " ".join(results)

    def test_as_filters_by_prefix(self):
        c = self._completer()
        results = self._complete(c, "/as co")
        assert any("coder" in r for r in results)
        assert not any("tester" in r for r in results)

    def test_whois_completes_agents(self):
        c = self._completer()
        results = self._complete(c, "/whois ")
        assert any("coder" in r for r in results)

    def test_lock_completes_agents(self):
        c = self._completer()
        results = self._complete(c, "/lock ")
        assert any("coder" in r for r in results)

    def test_help_completes_commands(self):
        c = self._completer()
        results = self._complete(c, "/help ")
        assert any("status" in r for r in results)

    def test_regular_slash_still_works(self):
        c = self._completer()
        results = self._complete(c, "/cl")
        assert any("clear" in r for r in results)

    def test_at_agent_completion_unchanged(self):
        c = self._completer()
        results = self._complete(c, "@co")
        assert any("coder" in r for r in results)

    def test_empty_prefix_after_as_returns_all_agents(self):
        c = self._completer()
        results = self._complete(c, "/as ")
        assert len(results) == 4  # all 4 agents

    def test_no_extra_space_for_help_completions(self):
        c = self._completer(commands=["help", "status", "clear"])
        results = self._complete(c, "/help cl")
        # "clear" — no trailing space for help completions
        assert "clear" in results


# ── Task 169: /alias ──────────────────────────────────────────────────────────

class TestAliasCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("alias") is not None

    def test_default_aliases_empty(self):
        reg = _make_registry()
        assert reg._aliases == {}

    def test_define_alias(self):
        reg = _make_registry()
        _run(reg.get("alias").handler(arg="tf /as tester fix tests"))
        assert "tf" in reg._aliases

    def test_alias_stores_command(self):
        reg = _make_registry()
        _run(reg.get("alias").handler(arg="tf /as tester fix tests"))
        assert reg._aliases["tf"] == "/as tester fix tests"

    def test_list_empty_aliases(self):
        reg = _make_registry()
        result = _run(reg.get("alias").handler(arg=""))
        assert "не определены" in result or "defined" in result.lower()

    def test_list_aliases(self):
        reg = _make_registry()
        reg._aliases["tf"] = "/as tester fix"
        reg._aliases["cr"] = "/as coder review"
        result = _run(reg.get("alias").handler(arg=""))
        assert "tf" in result
        assert "cr" in result

    def test_show_single_alias(self):
        reg = _make_registry()
        reg._aliases["tf"] = "/as tester fix"
        result = _run(reg.get("alias").handler(arg="tf"))
        assert "/as tester fix" in result

    def test_show_unknown_alias(self):
        reg = _make_registry()
        result = _run(reg.get("alias").handler(arg="zzz"))
        assert "не найден" in result or "not found" in result.lower()

    def test_clear_all_aliases(self):
        reg = _make_registry()
        reg._aliases["a"] = "/clear"
        reg._aliases["b"] = "/status"
        _run(reg.get("alias").handler(arg="clear"))
        assert reg._aliases == {}

    def test_define_without_slash_prefix(self):
        # /alias tf as tester fix — should auto-prefix the command
        reg = _make_registry()
        _run(reg.get("alias").handler(arg="tf as tester fix"))
        assert reg._aliases["tf"].startswith("/")

    def test_returns_confirmation_on_define(self):
        reg = _make_registry()
        result = _run(reg.get("alias").handler(arg="tf /as tester fix"))
        assert "tf" in result
        assert "создан" in result or "→" in result


# ── alias expansion in process_slash_command ──────────────────────────────────

class TestAliasExpansion:
    def test_alias_expands_to_known_command(self):
        import asyncio
        from io import StringIO
        from rich.console import Console
        from lidco.cli.app import process_slash_command
        from lidco.cli.renderer import Renderer

        buf = StringIO()
        renderer = Renderer(Console(file=buf, force_terminal=True, width=120))
        reg = _make_registry()
        reg._aliases["h"] = "/help"

        result = asyncio.run(process_slash_command("/h", reg, renderer))
        # Should have executed /help successfully
        assert result[0] is True  # should_continue
