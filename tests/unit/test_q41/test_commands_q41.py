"""Tests for Q41 slash commands (Tasks 276–285)."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.cli.commands import CommandRegistry


def _make_registry(tmp_path=None) -> CommandRegistry:
    reg = CommandRegistry()
    session = MagicMock()
    session.config = MagicMock()
    session.config.llm = MagicMock()
    session.config.llm.default_model = "claude-sonnet-4-6"
    session.config.agents = MagicMock()
    session.config.agents.context_window = 128000
    session.llm = MagicMock()
    session.llm.set_default_model = MagicMock()
    session.token_budget = MagicMock()
    session.token_budget._stats = None
    orch = MagicMock()
    orch._conversation_history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    session.orchestrator = orch
    reg.set_session(session)
    return reg


# ── /compact ─────────────────────────────────────────────────────────────────

class TestCompactCommand:
    def test_compact_empty_history(self):
        reg = _make_registry()
        reg._session.orchestrator._conversation_history = []
        result = asyncio.run(reg.get("compact").handler(arg="--llm"))
        assert "empty" in result.lower()

    def test_compact_calls_llm(self):
        reg = _make_registry()
        llm = reg._session.llm
        resp = MagicMock()
        resp.content = "Summary of conversation."
        llm.complete = AsyncMock(return_value=resp)

        result = asyncio.run(reg.get("compact").handler(arg="--llm"))
        llm.complete.assert_called_once()
        assert "Summary" in result

    def test_compact_replaces_history(self):
        reg = _make_registry()
        llm = reg._session.llm
        resp = MagicMock()
        resp.content = "Compacted."
        llm.complete = AsyncMock(return_value=resp)

        asyncio.run(reg.get("compact").handler(arg="--llm"))
        history = reg._session.orchestrator._conversation_history
        assert len(history) == 1
        assert "Compacted" in history[0]["content"]

    def test_compact_with_focus_hint(self):
        reg = _make_registry()
        llm = reg._session.llm
        resp = MagicMock()
        resp.content = "Summary."
        llm.complete = AsyncMock(return_value=resp)

        asyncio.run(reg.get("compact").handler(arg="--llm auth flow"))
        call_args = llm.complete.call_args[1]
        messages = call_args.get("messages") or llm.complete.call_args[0][0]
        system_msg = messages[0]["content"]
        assert "auth flow" in system_msg

    def test_compact_no_session(self):
        reg = _make_registry()
        reg._session = None
        result = asyncio.run(reg.get("compact").handler(arg=""))
        assert "No active session" in result


# ── /context ──────────────────────────────────────────────────────────────────

class TestContextCommand:
    def test_context_shows_percentage(self):
        reg = _make_registry()
        result = asyncio.run(reg.get("context").handler(arg=""))
        assert "%" in result

    def test_context_shows_bar(self):
        reg = _make_registry()
        result = asyncio.run(reg.get("context").handler(arg=""))
        assert "█" in result or "░" in result or "[" in result

    def test_context_shows_limit(self):
        reg = _make_registry()
        result = asyncio.run(reg.get("context").handler(arg=""))
        assert "128" in result  # 128k limit


# ── /mention ──────────────────────────────────────────────────────────────────

class TestMentionCommand:
    def test_mention_nonexistent_file(self):
        reg = _make_registry()
        result = asyncio.run(reg.get("mention").handler(arg="/no/such/file.py"))
        assert "not found" in result.lower()

    def test_mention_existing_file(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("print('hello')")
        reg = _make_registry()
        result = asyncio.run(reg.get("mention").handler(arg=str(f)))
        assert "injected" in result.lower() or "next" in result.lower()
        assert str(f) in reg._mentions

    def test_mention_no_arg_shows_list(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x")
        reg = _make_registry()
        reg._mentions = [str(f)]
        result = asyncio.run(reg.get("mention").handler(arg=""))
        assert str(f) in result

    def test_mention_no_arg_empty(self):
        reg = _make_registry()
        result = asyncio.run(reg.get("mention").handler(arg=""))
        assert "No files mentioned" in result

    def test_mention_no_duplicate(self, tmp_path):
        f = tmp_path / "b.py"
        f.write_text("x")
        reg = _make_registry()
        asyncio.run(reg.get("mention").handler(arg=str(f)))
        asyncio.run(reg.get("mention").handler(arg=str(f)))
        assert reg._mentions.count(str(f)) == 1


# ── /model ───────────────────────────────────────────────────────────────────

class TestModelCommand:
    def test_model_no_arg_shows_current(self):
        reg = _make_registry()
        result = asyncio.run(reg.get("model").handler(arg=""))
        assert "claude-sonnet-4-6" in result

    def test_model_switch(self):
        reg = _make_registry()
        result = asyncio.run(reg.get("model").handler(arg="claude-opus-4-6"))
        assert "claude-opus-4-6" in result
        assert reg._session.config.llm.default_model == "claude-opus-4-6"
        reg._session.llm.set_default_model.assert_called_with("claude-opus-4-6")


# ── /theme ───────────────────────────────────────────────────────────────────

class TestThemeCommand:
    def test_theme_list(self):
        reg = _make_registry()
        result = asyncio.run(reg.get("theme").handler(arg=""))
        assert "dark" in result
        assert "light" in result
        assert "nord" in result

    def test_theme_switch_valid(self):
        reg = _make_registry()
        result = asyncio.run(reg.get("theme").handler(arg="nord"))
        assert "Nord" in result
        assert reg._theme == "nord"

    def test_theme_switch_invalid(self):
        reg = _make_registry()
        result = asyncio.run(reg.get("theme").handler(arg="rainbow"))
        assert "Unknown theme" in result

    def test_theme_default_is_dark(self):
        reg = _make_registry()
        assert reg._theme == "dark"


# ── /add-dir ─────────────────────────────────────────────────────────────────

class TestAddDirCommand:
    def test_add_dir_nonexistent(self):
        reg = _make_registry()
        result = asyncio.run(reg.get("add-dir").handler(arg="/no/such/dir"))
        assert "not found" in result.lower()

    def test_add_dir_valid(self, tmp_path):
        reg = _make_registry()
        result = asyncio.run(reg.get("add-dir").handler(arg=str(tmp_path)))
        assert str(tmp_path.resolve()) in reg._extra_dirs

    def test_add_dir_not_a_dir(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x")
        reg = _make_registry()
        result = asyncio.run(reg.get("add-dir").handler(arg=str(f)))
        assert "not a directory" in result.lower()

    def test_add_dir_no_duplicate(self, tmp_path):
        reg = _make_registry()
        asyncio.run(reg.get("add-dir").handler(arg=str(tmp_path)))
        asyncio.run(reg.get("add-dir").handler(arg=str(tmp_path)))
        assert reg._extra_dirs.count(str(tmp_path.resolve())) == 1

    def test_add_dir_list_when_empty(self):
        reg = _make_registry()
        result = asyncio.run(reg.get("add-dir").handler(arg=""))
        assert "No extra directories" in result


# ── /checkpoint ──────────────────────────────────────────────────────────────

class TestCheckpointCommand:
    def _reg_with_mgr(self):
        reg = _make_registry()
        from lidco.cli.checkpoint import CheckpointManager
        reg._checkpoint_mgr = CheckpointManager()
        return reg

    def test_checkpoint_list_empty(self):
        reg = self._reg_with_mgr()
        result = asyncio.run(reg.get("checkpoint").handler(arg=""))
        assert "No checkpoints" in result

    def test_checkpoint_list_with_entries(self, tmp_path):
        reg = self._reg_with_mgr()
        reg._checkpoint_mgr.record("/a.py", "old")
        result = asyncio.run(reg.get("checkpoint").handler(arg="list"))
        assert "a.py" in result

    def test_checkpoint_undo(self, tmp_path):
        p = tmp_path / "x.py"
        p.write_text("new")
        reg = self._reg_with_mgr()
        reg._checkpoint_mgr.record(str(p), "old")
        result = asyncio.run(reg.get("checkpoint").handler(arg="undo 1"))
        assert "Restored" in result
        assert p.read_text() == "old"

    def test_checkpoint_undo_nothing(self):
        reg = self._reg_with_mgr()
        result = asyncio.run(reg.get("checkpoint").handler(arg="undo"))
        assert "Nothing to undo" in result

    def test_checkpoint_clear(self):
        reg = self._reg_with_mgr()
        reg._checkpoint_mgr.record("/a.py", "old")
        result = asyncio.run(reg.get("checkpoint").handler(arg="clear"))
        assert "cleared" in result.lower()
        assert reg._checkpoint_mgr.count() == 0

    def test_checkpoint_no_mgr(self):
        reg = _make_registry()
        reg._checkpoint_mgr = None
        result = asyncio.run(reg.get("checkpoint").handler(arg=""))
        assert "not initialized" in result.lower()


# ── /session ─────────────────────────────────────────────────────────────────

class TestSessionCommand:
    def _reg_with_store(self, tmp_path):
        from lidco.cli.session_store import SessionStore
        reg = _make_registry()
        reg._session_store = SessionStore(base_dir=tmp_path / "sessions")
        return reg

    def test_session_list_empty(self, tmp_path):
        reg = self._reg_with_store(tmp_path)
        result = asyncio.run(reg.get("session").handler(arg="list"))
        assert "No saved sessions" in result

    def test_session_save(self, tmp_path):
        reg = self._reg_with_store(tmp_path)
        result = asyncio.run(reg.get("session").handler(arg="save"))
        assert "saved" in result.lower()

    def test_session_save_with_id(self, tmp_path):
        reg = self._reg_with_store(tmp_path)
        result = asyncio.run(reg.get("session").handler(arg="save mysession"))
        assert "mysession" in result

    def test_session_load(self, tmp_path):
        reg = self._reg_with_store(tmp_path)
        reg._session_store.save([{"role": "user", "content": "test"}], session_id="s1")
        result = asyncio.run(reg.get("session").handler(arg="load s1"))
        assert "s1" in result
        assert "loaded" in result.lower()

    def test_session_load_nonexistent(self, tmp_path):
        reg = self._reg_with_store(tmp_path)
        result = asyncio.run(reg.get("session").handler(arg="load ghost"))
        assert "not found" in result.lower()

    def test_session_delete(self, tmp_path):
        reg = self._reg_with_store(tmp_path)
        reg._session_store.save([], session_id="del-me")
        result = asyncio.run(reg.get("session").handler(arg="delete del-me"))
        assert "deleted" in result.lower()

    def test_session_list_after_save(self, tmp_path):
        reg = self._reg_with_store(tmp_path)
        asyncio.run(reg.get("session").handler(arg="save listed"))
        result = asyncio.run(reg.get("session").handler(arg="list"))
        assert "listed" in result
