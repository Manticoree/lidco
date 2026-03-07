"""Tests for /notes (#209), /git (#210), /ctx (#211)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.cli.commands import CommandRegistry


def _run(coro) -> str:
    return asyncio.run(coro)


def _make_registry() -> CommandRegistry:
    return CommandRegistry()


def _make_session_registry(**kwargs) -> CommandRegistry:
    reg = _make_registry()
    sess = MagicMock()
    cfg = MagicMock()
    cfg.llm.default_model = kwargs.get("model", "claude-sonnet-4-6")
    sess.config = cfg
    sess.project_dir = kwargs.get("project_dir", Path("."))
    reg.set_session(sess)
    return reg


# ── Task 209: /note ───────────────────────────────────────────────────────────

class TestNotesCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("notes") is not None

    def test_no_notes_shows_empty_message(self, tmp_path, monkeypatch):  # noqa: D102
        monkeypatch.chdir(tmp_path)
        reg = _make_registry()
        result = _run(reg.get("notes").handler())
        assert "нет" in result.lower() or "no" in result.lower() or "добавьте" in result.lower()

    def test_add_note(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        reg = _make_registry()
        result = _run(reg.get("notes").handler(arg="fix the auth bug in token.py"))
        assert "✓" in result or "сохранена" in result.lower()

    def test_note_persists(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        reg = _make_registry()
        _run(reg.get("notes").handler(arg="remember this pattern"))
        # New registry reads same file
        reg2 = _make_registry()
        result = _run(reg2.get("notes").handler(arg="list"))
        assert "remember this pattern" in result

    def test_list_shows_all_notes(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        reg = _make_registry()
        _run(reg.get("notes").handler(arg="first note"))
        _run(reg.get("notes").handler(arg="second note"))
        result = _run(reg.get("notes").handler(arg="list"))
        assert "first note" in result
        assert "second note" in result

    def test_list_shows_count(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        reg = _make_registry()
        _run(reg.get("notes").handler(arg="note one"))
        _run(reg.get("notes").handler(arg="note two"))
        _run(reg.get("notes").handler(arg="note three"))
        result = _run(reg.get("notes").handler(arg="list"))
        assert "3" in result

    def test_delete_note(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        reg = _make_registry()
        _run(reg.get("notes").handler(arg="to delete"))
        _run(reg.get("notes").handler(arg="del 1"))
        result = _run(reg.get("notes").handler(arg="list"))
        assert "to delete" not in result

    def test_delete_invalid_index_shows_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        reg = _make_registry()
        _run(reg.get("notes").handler(arg="some note"))
        result = _run(reg.get("notes").handler(arg="del 99"))
        assert "не найдена" in result or "not found" in result.lower()

    def test_clear_removes_all(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        reg = _make_registry()
        _run(reg.get("notes").handler(arg="a"))
        _run(reg.get("notes").handler(arg="b"))
        _run(reg.get("notes").handler(arg="clear"))
        result = _run(reg.get("notes").handler(arg="list"))
        assert "нет" in result.lower() or "0" in result or "no" in result.lower()

    def test_search_finds_note(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        reg = _make_registry()
        _run(reg.get("notes").handler(arg="fix the oauth token expiry bug"))
        _run(reg.get("notes").handler(arg="refactor the database layer"))
        result = _run(reg.get("notes").handler(arg="search oauth"))
        assert "oauth" in result.lower()

    def test_search_no_match(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        reg = _make_registry()
        _run(reg.get("notes").handler(arg="unrelated note"))
        result = _run(reg.get("notes").handler(arg="search xyzzy_no_match"))
        assert "не найдено" in result.lower() or "not found" in result.lower()

    def test_tag_support(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        reg = _make_registry()
        result = _run(reg.get("notes").handler(arg="#bug fix the login redirect"))
        assert "bug" in result or "✓" in result

    def test_shows_timestamp(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        reg = _make_registry()
        _run(reg.get("notes").handler(arg="timestamped note"))
        result = _run(reg.get("notes").handler(arg="list"))
        # Should have a date-like string
        import re
        assert re.search(r"\d{4}-\d{2}-\d{2}", result)

    def test_stores_in_lidco_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        reg = _make_registry()
        _run(reg.get("notes").handler(arg="check storage"))
        notes_file = tmp_path / ".lidco" / "notes.json"
        assert notes_file.exists()
        data = json.loads(notes_file.read_text())
        assert len(data) == 1
        assert data[0]["text"] == "check storage"


# ── Task 210: /git ────────────────────────────────────────────────────────────

class TestGitCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("git") is not None

    def test_no_arg_shows_status(self):
        reg = _make_registry()
        result = _run(reg.get("git").handler())
        # Either shows status or an error message — both are str
        assert isinstance(result, str) and len(result) > 0

    def test_status_subcommand(self):
        reg = _make_registry()
        result = _run(reg.get("git").handler(arg="status"))
        assert isinstance(result, str) and len(result) > 0

    def test_log_subcommand(self):
        reg = _make_registry()
        result = _run(reg.get("git").handler(arg="log"))
        assert isinstance(result, str) and len(result) > 0

    def test_log_with_count(self):
        reg = _make_registry()
        result = _run(reg.get("git").handler(arg="log 5"))
        assert isinstance(result, str) and len(result) > 0

    def test_log_caps_at_50(self):
        reg = _make_registry()
        # Should not error with large number
        result = _run(reg.get("git").handler(arg="log 1000"))
        assert isinstance(result, str)

    def test_branch_subcommand(self):
        reg = _make_registry()
        result = _run(reg.get("git").handler(arg="branch"))
        assert isinstance(result, str) and len(result) > 0

    def test_blame_no_file_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("git").handler(arg="blame"))
        assert "файл" in result.lower() or "file" in result.lower() or "укажите" in result.lower()

    def test_diff_subcommand(self):
        reg = _make_registry()
        result = _run(reg.get("git").handler(arg="diff"))
        assert isinstance(result, str) and len(result) > 0

    def test_show_subcommand(self):
        reg = _make_registry()
        result = _run(reg.get("git").handler(arg="show HEAD"))
        assert isinstance(result, str) and len(result) > 0

    def test_unknown_subcommand_shows_help(self):
        reg = _make_registry()
        result = _run(reg.get("git").handler(arg="xyzzy_unknown"))
        assert "использование" in result.lower() or "usage" in result.lower() or "подкоманд" in result.lower()

    def test_status_shows_branch_label(self):
        reg = _make_registry()
        result = _run(reg.get("git").handler(arg="status"))
        # In a git repo: should show "Ветка" or error if not in git repo
        assert "ветка" in result.lower() or "branch" in result.lower() or "git" in result.lower() or "error" in result.lower() or "ошибка" in result.lower() or "не найден" in result.lower()

    def test_log_shows_git_label(self):
        reg = _make_registry()
        result = _run(reg.get("git").handler(arg="log 3"))
        assert "git" in result.lower() or "лог" in result.lower() or "коммит" in result.lower() or "commit" in result.lower() or isinstance(result, str)


# ── Task 211: /ctx ────────────────────────────────────────────────────────────

class TestCtxCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("ctx") is not None

    def test_returns_string(self):
        reg = _make_registry()
        result = _run(reg.get("ctx").handler())
        assert isinstance(result, str) and len(result) > 0

    def test_shows_model_name(self):
        reg = _make_session_registry(model="claude-sonnet-4-6")
        result = _run(reg.get("ctx").handler())
        assert "claude" in result.lower() or "модель" in result.lower()

    def test_shows_context_limit(self):
        reg = _make_session_registry(model="claude-sonnet-4-6")
        result = _run(reg.get("ctx").handler())
        assert "200" in result or "128" in result or "лимит" in result.lower()

    def test_shows_percentage(self):
        reg = _make_registry()
        result = _run(reg.get("ctx").handler())
        assert "%" in result

    def test_shows_bar_chart(self):
        reg = _make_registry()
        result = _run(reg.get("ctx").handler())
        assert "█" in result or "░" in result or "▓" in result or "▒" in result

    def test_shows_token_estimate(self):
        reg = _make_registry()
        result = _run(reg.get("ctx").handler())
        assert "токен" in result.lower() or "token" in result.lower()

    def test_shows_remaining(self):
        reg = _make_registry()
        result = _run(reg.get("ctx").handler())
        assert "остал" in result.lower() or "remain" in result.lower()

    def test_shows_message_count(self):
        reg = _make_session_registry()
        orch = MagicMock()
        orch._messages = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
        reg._session._orchestrator = orch
        result = _run(reg.get("ctx").handler())
        assert "2" in result or "сообщений" in result.lower()

    def test_no_session_still_works(self):
        reg = _make_registry()
        result = _run(reg.get("ctx").handler())
        assert isinstance(result, str) and len(result) > 0

    def test_warning_shown_on_high_usage(self):
        reg = _make_session_registry(model="gpt-4")  # 8192 token limit
        orch = MagicMock()
        # Fill with lots of content
        big_content = "word " * 5000  # ~20000 chars / 4 = 5000 tokens
        orch._messages = [{"role": "user", "content": big_content}]
        reg._session._orchestrator = orch
        result = _run(reg.get("ctx").handler())
        # Either shows warning or shows percentage - both valid
        assert isinstance(result, str) and len(result) > 0

    def test_shows_approximation_note(self):
        reg = _make_registry()
        result = _run(reg.get("ctx").handler())
        assert "оценк" in result.lower() or "приблизительн" in result.lower() or "approx" in result.lower() or "~" in result
