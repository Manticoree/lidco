"""Tests for /watch (#179), /tag (#180), /summary (#181)."""

from __future__ import annotations

import asyncio
import time
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
    orch = MagicMock()
    orch._conversation_history = kwargs.get("history", [])
    orch.restore_history = MagicMock()
    sess.orchestrator = orch
    reg.set_session(sess)
    return reg


# ── Task 179: /watch ──────────────────────────────────────────────────────────

class TestWatchCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("watch") is not None

    def test_default_watched_empty(self):
        reg = _make_registry()
        assert reg._watched_files == []
        assert reg._watch_snapshot == {}

    def test_no_arg_shows_empty_message(self):
        reg = _make_registry()
        result = _run(reg.get("watch").handler())
        assert "нет" in result.lower() or "no" in result.lower() or "отслеживаемых" in result.lower()

    def test_add_existing_file(self, tmp_path):
        f = tmp_path / "watch_me.py"
        f.write_text("x = 1")
        reg = _make_registry()
        result = _run(reg.get("watch").handler(arg=f"add {f}"))
        assert str(f) in reg._watched_files
        assert "начато" in result.lower() or "watch" in result.lower() or str(f) in result

    def test_add_records_mtime(self, tmp_path):
        f = tmp_path / "timed.py"
        f.write_text("y = 2")
        reg = _make_registry()
        _run(reg.get("watch").handler(arg=f"add {f}"))
        assert str(f) in reg._watch_snapshot
        assert reg._watch_snapshot[str(f)] > 0

    def test_add_nonexistent_file_returns_error(self):
        reg = _make_registry()
        result = _run(reg.get("watch").handler(arg="add /nonexistent/file.py"))
        assert "не найден" in result or "not found" in result.lower()

    def test_add_duplicate_file_warns(self, tmp_path):
        f = tmp_path / "dup.py"
        f.write_text("z = 3")
        reg = _make_registry()
        _run(reg.get("watch").handler(arg=f"add {f}"))
        result = _run(reg.get("watch").handler(arg=f"add {f}"))
        assert "уже" in result or "already" in result.lower()

    def test_list_shows_watched_files(self, tmp_path):
        f = tmp_path / "listed.py"
        f.write_text("a = 1")
        reg = _make_registry()
        reg._watched_files.append(str(f))
        reg._watch_snapshot[str(f)] = f.stat().st_mtime
        result = _run(reg.get("watch").handler(arg="list"))
        assert str(f) in result

    def test_remove_file(self, tmp_path):
        f = tmp_path / "removeme.py"
        f.write_text("b = 2")
        reg = _make_registry()
        path_str = str(f)
        reg._watched_files.append(path_str)
        reg._watch_snapshot[path_str] = 0.0
        _run(reg.get("watch").handler(arg=f"remove {path_str}"))
        assert path_str not in reg._watched_files
        assert path_str not in reg._watch_snapshot

    def test_remove_nonwatched_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("watch").handler(arg="remove /some/file.py"))
        assert "не отслеживается" in result or "not" in result.lower()

    def test_clear_removes_all(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("a")
        f2.write_text("b")
        reg = _make_registry()
        for f in [f1, f2]:
            reg._watched_files.append(str(f))
            reg._watch_snapshot[str(f)] = 0.0
        _run(reg.get("watch").handler(arg="clear"))
        assert reg._watched_files == []
        assert reg._watch_snapshot == {}

    def test_clear_returns_count(self, tmp_path):
        f = tmp_path / "c.py"
        f.write_text("c")
        reg = _make_registry()
        reg._watched_files.extend([str(f), "other.py"])
        result = _run(reg.get("watch").handler(arg="clear"))
        assert "2" in result

    def test_check_detects_change(self, tmp_path):
        f = tmp_path / "changed.py"
        f.write_text("old content")
        reg = _make_registry()
        reg._watched_files.append(str(f))
        reg._watch_snapshot[str(f)] = 0.0  # old mtime (epoch)
        result = _run(reg.get("watch").handler(arg="check"))
        assert "changed.py" in result or "изменено" in result.lower() or "1" in result

    def test_check_no_changes(self, tmp_path):
        f = tmp_path / "static.py"
        f.write_text("static")
        reg = _make_registry()
        reg._watched_files.append(str(f))
        reg._watch_snapshot[str(f)] = f.stat().st_mtime
        result = _run(reg.get("watch").handler(arg="check"))
        assert "нет" in result.lower() or "no" in result.lower() or "изменений" in result.lower()

    def test_check_updates_snapshot(self, tmp_path):
        f = tmp_path / "update.py"
        f.write_text("v1")
        reg = _make_registry()
        reg._watched_files.append(str(f))
        reg._watch_snapshot[str(f)] = 0.0
        _run(reg.get("watch").handler(arg="check"))
        # After check, snapshot should be updated to current mtime
        assert reg._watch_snapshot[str(f)] != 0.0


# ── Task 180: /tag ────────────────────────────────────────────────────────────

class TestTagCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("tag") is not None

    def test_default_tags_empty(self):
        reg = _make_registry()
        assert reg._tags == {}

    def test_no_arg_shows_empty_message(self):
        reg = _make_registry()
        result = _run(reg.get("tag").handler())
        assert "нет" in result.lower() or "no" in result.lower() or "тегов" in result.lower()

    def test_add_tag(self):
        reg = _make_registry()
        _run(reg.get("tag").handler(arg="add checkpoint"))
        assert "checkpoint" in reg._tags

    def test_add_returns_confirmation(self):
        reg = _make_registry()
        result = _run(reg.get("tag").handler(arg="add v1"))
        assert "v1" in result or "установлен" in result.lower()

    def test_add_invalid_label(self):
        reg = _make_registry()
        result = _run(reg.get("tag").handler(arg="add my label with spaces"))
        # Spaces are invalid
        assert "недопустим" in result.lower() or "invalid" in result.lower() or "символ" in result.lower()

    def test_list_shows_tags(self):
        reg = _make_registry()
        reg._tags = {"v1": 4, "checkpoint": 10}
        result = _run(reg.get("tag").handler(arg="list"))
        assert "v1" in result
        assert "checkpoint" in result

    def test_del_removes_tag(self):
        reg = _make_registry()
        reg._tags["old"] = 3
        _run(reg.get("tag").handler(arg="del old"))
        assert "old" not in reg._tags

    def test_del_nonexistent_tag(self):
        reg = _make_registry()
        result = _run(reg.get("tag").handler(arg="del ghost"))
        assert "не найден" in result or "not found" in result.lower()

    def test_clear_removes_all(self):
        reg = _make_registry()
        reg._tags = {"a": 1, "b": 2}
        _run(reg.get("tag").handler(arg="clear"))
        assert reg._tags == {}

    def test_jump_restores_history(self):
        history = [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "reply1"},
            {"role": "user", "content": "msg2"},
            {"role": "assistant", "content": "reply2"},
        ]
        reg = _make_session_registry(history=history)
        reg._tags["before_msg2"] = 2  # after first pair
        _run(reg.get("tag").handler(arg="jump before_msg2"))
        reg._session.orchestrator.restore_history.assert_called_once_with(history[:2])

    def test_jump_nonexistent_tag(self):
        reg = _make_session_registry()
        result = _run(reg.get("tag").handler(arg="jump ghost"))
        assert "не найден" in result or "not found" in result.lower()

    def test_jump_shows_available_tags(self):
        reg = _make_session_registry()
        reg._tags["v1"] = 2
        result = _run(reg.get("tag").handler(arg="jump ghost"))
        assert "v1" in result

    def test_bare_word_adds_tag(self):
        reg = _make_registry()
        reg._turn_times = [1.0, 2.0]
        _run(reg.get("tag").handler(arg="mymark"))
        assert "mymark" in reg._tags
        assert reg._tags["mymark"] == 2

    def test_tag_stores_history_length(self):
        history = [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}]
        reg = _make_session_registry(history=history)
        _run(reg.get("tag").handler(arg="add here"))
        assert reg._tags["here"] == 2


# ── Task 181: /summary ────────────────────────────────────────────────────────

class TestSummaryCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("summary") is not None

    def test_no_session_returns_error(self):
        reg = _make_registry()
        result = _run(reg.get("summary").handler())
        assert "не инициализирована" in result or "not initialized" in result.lower()

    def test_empty_history_returns_message(self):
        reg = _make_session_registry(history=[])
        result = _run(reg.get("summary").handler())
        assert "пуста" in result or "empty" in result.lower()

    def test_calls_llm_with_transcript(self):
        history = [
            {"role": "user", "content": "Fix the bug in auth.py"},
            {"role": "assistant", "content": "I found the issue on line 42."},
        ]
        reg = _make_session_registry(history=history)

        mock_resp = MagicMock()
        mock_resp.content = "- Fixed auth bug on line 42\n- Reviewed auth.py"
        reg._session.llm.complete = AsyncMock(return_value=mock_resp)

        result = _run(reg.get("summary").handler())
        assert "Fixed auth" in result or "auth" in result.lower()

    def test_shows_turn_count(self):
        history = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"},
            {"role": "assistant", "content": "a2"},
        ]
        reg = _make_session_registry(history=history)
        mock_resp = MagicMock()
        mock_resp.content = "- Two questions answered"
        reg._session.llm.complete = AsyncMock(return_value=mock_resp)
        result = _run(reg.get("summary").handler())
        assert "2" in result  # 2 user turns

    def test_handles_llm_error(self):
        history = [{"role": "user", "content": "hello"}]
        reg = _make_session_registry(history=history)
        reg._session.llm.complete = AsyncMock(side_effect=Exception("LLM unavailable"))
        result = _run(reg.get("summary").handler())
        assert "не удалось" in result.lower() or "failed" in result.lower() or "unavailable" in result

    def test_shows_navigation_hints(self):
        history = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]
        reg = _make_session_registry(history=history)
        mock_resp = MagicMock()
        mock_resp.content = "- Done"
        reg._session.llm.complete = AsyncMock(return_value=mock_resp)
        result = _run(reg.get("summary").handler())
        assert "/history" in result or "/compact" in result
