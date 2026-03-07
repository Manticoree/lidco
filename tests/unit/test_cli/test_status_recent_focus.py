"""Tests for enhanced /status (#170), /recent (#171), /focus (#172)."""

from __future__ import annotations

import asyncio
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from lidco.cli.commands import CommandRegistry


def _run(coro) -> str:
    return asyncio.run(coro)


def _make_registry() -> CommandRegistry:
    return CommandRegistry()


def _make_session_registry(**kwargs) -> CommandRegistry:
    reg = _make_registry()
    sess = MagicMock()
    tb = MagicMock()
    tb._total_tokens = kwargs.get("tokens", 0)
    tb._total_prompt_tokens = 0
    tb._total_completion_tokens = 0
    tb._total_cost_usd = 0.0
    tb._by_role = {}
    tb.session_limit = 0
    sess.token_budget = tb
    mem = MagicMock()
    mem.list_all.return_value = []
    sess.memory = mem
    tool_reg = MagicMock()
    tool_reg.list_tools.return_value = []
    sess.tool_registry = tool_reg
    cfg = MagicMock()
    cfg.llm.default_model = "gpt-4"
    sess.config = cfg
    sess.debug_mode = False
    orch = MagicMock()
    orch._conversation_history = kwargs.get("history", [])
    sess.orchestrator = orch
    reg.set_session(sess)
    return reg


# ── Task 170: enhanced /status ────────────────────────────────────────────────

class TestEnhancedStatus:
    def test_shows_history_length(self):
        reg = _make_session_registry(history=["a", "b", "c"])
        result = _run(reg.get("status").handler())
        assert "3" in result  # 3 history messages

    def test_shows_locked_agent(self):
        reg = _make_session_registry()
        reg.locked_agent = "coder"
        result = _run(reg.get("status").handler())
        assert "coder" in result
        assert "lock" in result.lower() or "Locked" in result

    def test_no_locked_agent_no_lock_line(self):
        reg = _make_session_registry()
        reg.locked_agent = None
        result = _run(reg.get("status").handler())
        assert "Locked" not in result

    def test_shows_session_note(self):
        reg = _make_session_registry()
        reg.session_note = "use asyncio everywhere"
        result = _run(reg.get("status").handler())
        assert "use asyncio" in result

    def test_no_note_no_note_line(self):
        reg = _make_session_registry()
        reg.session_note = ""
        result = _run(reg.get("status").handler())
        assert "Note:" not in result

    def test_shows_aliases(self):
        reg = _make_session_registry()
        reg._aliases = {"tf": "/as tester", "cr": "/as coder"}
        result = _run(reg.get("status").handler())
        assert "tf" in result or "cr" in result

    def test_shows_edited_count(self):
        reg = _make_session_registry()
        reg._edited_files = ["a.py", "b.py", "a.py"]
        result = _run(reg.get("status").handler())
        assert "2" in result  # 2 unique files

    def test_shows_focus_file(self):
        reg = _make_session_registry()
        reg.focus_file = "src/main.py"
        result = _run(reg.get("status").handler())
        assert "src/main.py" in result


# ── Task 171: /recent ─────────────────────────────────────────────────────────

class TestRecentCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("recent") is not None

    def test_empty_returns_message(self):
        reg = _make_registry()
        result = _run(reg.get("recent").handler())
        assert "не изменялись" in result or "no files" in result.lower()

    def test_shows_edited_files(self):
        reg = _make_registry()
        reg._edited_files = ["src/auth.py", "src/models.py"]
        result = _run(reg.get("recent").handler())
        assert "src/auth.py" in result
        assert "src/models.py" in result

    def test_deduplicates_files(self):
        reg = _make_registry()
        reg._edited_files = ["a.py", "b.py", "a.py", "b.py"]
        result = _run(reg.get("recent").handler())
        # Should show 2 unique files, not 4
        assert result.count("a.py") == 1
        assert result.count("b.py") == 1

    def test_respects_n_argument(self):
        reg = _make_registry()
        reg._edited_files = [f"file{i}.py" for i in range(20)]
        result = _run(reg.get("recent").handler(arg="3"))
        # Should show 3 files
        assert "3" in result

    def test_shows_undo_hint(self):
        reg = _make_registry()
        reg._edited_files = ["x.py"]
        result = _run(reg.get("recent").handler())
        assert "undo" in result.lower() or "diff" in result.lower()

    def test_preserves_insertion_order(self):
        reg = _make_registry()
        reg._edited_files = ["first.py", "second.py", "third.py"]
        result = _run(reg.get("recent").handler())
        pos_first = result.find("first.py")
        pos_third = result.find("third.py")
        assert pos_first < pos_third

    def test_invalid_n_defaults_to_10(self):
        reg = _make_registry()
        reg._edited_files = ["x.py"]
        result = _run(reg.get("recent").handler(arg="abc"))
        assert "x.py" in result


# ── Task 172: /focus ──────────────────────────────────────────────────────────

class TestFocusCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("focus") is not None

    def test_default_focus_empty(self):
        reg = _make_registry()
        assert reg.focus_file == ""

    def test_no_arg_shows_status_when_empty(self):
        reg = _make_registry()
        result = _run(reg.get("focus").handler())
        assert "не установлен" in result or "not set" in result.lower()

    def test_clear_when_not_set(self):
        reg = _make_registry()
        result = _run(reg.get("focus").handler(arg="clear"))
        assert reg.focus_file == ""
        assert "снят" in result or "clear" in result.lower()

    def test_nonexistent_file_returns_error(self):
        reg = _make_registry()
        result = _run(reg.get("focus").handler(arg="/nonexistent/file.py"))
        assert "не найден" in result or "not found" in result.lower()

    def test_existing_file_sets_focus(self, tmp_path):
        p = tmp_path / "focus.py"
        p.write_text("# focus content")
        reg = _make_registry()
        result = _run(reg.get("focus").handler(arg=str(p)))
        assert reg.focus_file == str(p)
        assert "фокус установлен" in result.lower() or str(p) in result

    def test_show_current_focus(self, tmp_path):
        p = tmp_path / "focused.py"
        p.write_text("x = 1")
        reg = _make_registry()
        reg.focus_file = str(p)
        result = _run(reg.get("focus").handler())
        assert str(p) in result

    def test_clear_removes_focus(self, tmp_path):
        p = tmp_path / "f.py"
        p.write_text("x")
        reg = _make_registry()
        reg.focus_file = str(p)
        _run(reg.get("focus").handler(arg="clear"))
        assert reg.focus_file == ""

    def test_directory_rejected(self, tmp_path):
        reg = _make_registry()
        result = _run(reg.get("focus").handler(arg=str(tmp_path)))
        assert "не файл" in result or "not a file" in result.lower()

    def test_shows_file_size(self, tmp_path):
        p = tmp_path / "big.py"
        p.write_text("x" * 100)
        reg = _make_registry()
        result = _run(reg.get("focus").handler(arg=str(p)))
        assert "100" in result or "байт" in result
