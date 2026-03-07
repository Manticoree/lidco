"""Tests for /snippet (#241), /todo (#242), /timer (#243)."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from lidco.cli.commands import CommandRegistry


def _run(coro) -> str:
    return asyncio.run(coro)


def _make_registry() -> CommandRegistry:
    return CommandRegistry()


# ── Task 241: /snippet ────────────────────────────────────────────────────────

class TestSnippetCommand:
    def test_registered(self):
        assert _make_registry().get("snippet") is not None

    def test_empty_shows_message(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = _run(_make_registry().get("snippet").handler())
        assert "нет" in result.lower() or "no" in result.lower() or "сниппет" in result.lower()

    def test_save_inline_code(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = _run(_make_registry().get("snippet").handler(arg="save mysnip x = 1"))
        assert "✅" in result or "сохранён" in result.lower()

    def test_save_from_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "util.py"
        f.write_text("def add(a, b): return a + b\n")
        result = _run(_make_registry().get("snippet").handler(arg=f"save addutil {f}"))
        assert "✅" in result or "сохранён" in result.lower()

    def test_save_stored_in_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("snippet").handler(arg="save mysnip x = 1"))
        data = json.loads((tmp_path / ".lidco" / "snippets.json").read_text())
        assert "mysnip" in data

    def test_show_snippet(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("snippet").handler(arg="save greet print('hello')"))
        result = _run(_make_registry().get("snippet").handler(arg="show greet"))
        assert "print" in result or "hello" in result

    def test_show_in_code_block(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("snippet").handler(arg="save block x = 42"))
        result = _run(_make_registry().get("snippet").handler(arg="show block"))
        assert "```" in result

    def test_list_shows_saved(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("snippet").handler(arg="save alpha x = 1"))
        _run(_make_registry().get("snippet").handler(arg="save beta y = 2"))
        result = _run(_make_registry().get("snippet").handler(arg="list"))
        assert "alpha" in result
        assert "beta" in result

    def test_del_removes_snippet(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("snippet").handler(arg="save todel x = 1"))
        result = _run(_make_registry().get("snippet").handler(arg="del todel"))
        assert "✓" in result or "удалён" in result.lower()

    def test_del_nonexistent_shows_warning(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = _run(_make_registry().get("snippet").handler(arg="del xyzzy_ghost"))
        assert "не найден" in result or "not found" in result.lower()

    def test_show_nonexistent_shows_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = _run(_make_registry().get("snippet").handler(arg="show nonexistent_snap"))
        assert "не найден" in result or "❌" in result

    def test_save_with_lang(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("snippet").handler(arg="save jssnip console.log(1) --lang js"))
        data = json.loads((tmp_path / ".lidco" / "snippets.json").read_text())
        assert data["jssnip"]["lang"] == "js"

    def test_save_with_desc(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("snippet").handler(arg="save mysnip x=1 --desc useful code"))
        data = json.loads((tmp_path / ".lidco" / "snippets.json").read_text())
        assert "useful" in data["mysnip"]["desc"]

    def test_clear_removes_all(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("snippet").handler(arg="save a x=1"))
        _run(_make_registry().get("snippet").handler(arg="save b y=2"))
        _run(_make_registry().get("snippet").handler(arg="clear"))
        data = json.loads((tmp_path / ".lidco" / "snippets.json").read_text())
        assert len(data) == 0

    def test_export_creates_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("snippet").handler(arg="save exportme x = 99"))
        out = tmp_path / "exported.py"
        result = _run(_make_registry().get("snippet").handler(arg=f"export exportme {out}"))
        assert out.exists()
        assert "99" in out.read_text()

    def test_export_existing_file_rejected(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("snippet").handler(arg="save ex x=1"))
        existing = tmp_path / "exists.py"
        existing.write_text("y = 2\n")
        result = _run(_make_registry().get("snippet").handler(arg=f"export ex {existing}"))
        assert "уже существует" in result or "exists" in result.lower()

    def test_shows_line_count(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("snippet").handler(arg="save counted a\nb\nc"))
        result = _run(_make_registry().get("snippet").handler(arg="list"))
        assert "1" in result or "строк" in result.lower()


# ── Task 242: /todo ───────────────────────────────────────────────────────────

class TestTodoCommand:
    def test_registered(self):
        assert _make_registry().get("todo") is not None

    def test_empty_shows_message(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = _run(_make_registry().get("todo").handler())
        assert "пуст" in result.lower() or "empty" in result.lower() or "нет" in result.lower()

    def test_add_todo(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = _run(_make_registry().get("todo").handler(arg="fix the auth bug"))
        assert "✓" in result or "добавлена" in result.lower()

    def test_todo_stored(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("todo").handler(arg="write unit tests"))
        data = json.loads((tmp_path / ".lidco" / "todos.json").read_text())
        assert any("unit tests" in t["text"] for t in data)

    def test_list_shows_pending(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("todo").handler(arg="task one"))
        _run(_make_registry().get("todo").handler(arg="task two"))
        result = _run(_make_registry().get("todo").handler())
        assert "task one" in result
        assert "task two" in result

    def test_shows_id(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = _run(_make_registry().get("todo").handler(arg="my task"))
        assert "#1" in result or "1" in result

    def test_done_marks_complete(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("todo").handler(arg="finish docs"))
        result = _run(_make_registry().get("todo").handler(arg="done 1"))
        assert "✅" in result or "выполнена" in result.lower()

    def test_done_hides_from_list(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("todo").handler(arg="done task"))
        _run(_make_registry().get("todo").handler(arg="done 1"))
        result = _run(_make_registry().get("todo").handler())
        assert "done task" not in result

    def test_all_shows_done_too(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("todo").handler(arg="completed item"))
        _run(_make_registry().get("todo").handler(arg="done 1"))
        result = _run(_make_registry().get("todo").handler(arg="all"))
        assert "completed item" in result

    def test_del_removes_todo(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("todo").handler(arg="delete me"))
        result = _run(_make_registry().get("todo").handler(arg="del 1"))
        assert "✓" in result or "удалена" in result.lower()

    def test_del_nonexistent_shows_warning(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = _run(_make_registry().get("todo").handler(arg="del 999"))
        assert "не найдена" in result or "not found" in result.lower()

    def test_clear_empties_list(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("todo").handler(arg="task a"))
        _run(_make_registry().get("todo").handler(arg="task b"))
        _run(_make_registry().get("todo").handler(arg="clear"))
        result = _run(_make_registry().get("todo").handler())
        assert "task a" not in result
        assert "task b" not in result

    def test_stats_shows_counts(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("todo").handler(arg="t1"))
        _run(_make_registry().get("todo").handler(arg="t2"))
        _run(_make_registry().get("todo").handler(arg="done 1"))
        result = _run(_make_registry().get("todo").handler(arg="stats"))
        assert "2" in result and "1" in result

    def test_stats_shows_percentage(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("todo").handler(arg="task"))
        _run(_make_registry().get("todo").handler(arg="done 1"))
        result = _run(_make_registry().get("todo").handler(arg="stats"))
        assert "%" in result or "100" in result

    def test_priority_high(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = _run(_make_registry().get("todo").handler(arg="!high fix the crash"))
        assert "HIGH" in result or "high" in result.lower() or "fix the crash" in result

    def test_search_finds_match(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("todo").handler(arg="write docs for auth"))
        _run(_make_registry().get("todo").handler(arg="fix login page"))
        result = _run(_make_registry().get("todo").handler(arg="search auth"))
        assert "auth" in result

    def test_undone_restores_task(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("todo").handler(arg="restore me"))
        _run(_make_registry().get("todo").handler(arg="done 1"))
        result = _run(_make_registry().get("todo").handler(arg="undone 1"))
        assert "↩️" in result or "возвращена" in result.lower()

    def test_ids_increment(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("todo").handler(arg="first"))
        result = _run(_make_registry().get("todo").handler(arg="second"))
        assert "#2" in result or "2" in result


# ── Task 243: /timer ──────────────────────────────────────────────────────────

class TestTimerCommand:
    def test_registered(self):
        assert _make_registry().get("timer") is not None

    def test_no_timers_shows_message(self):
        reg = _make_registry()
        result = _run(reg.get("timer").handler())
        assert "нет" in result.lower() or "no" in result.lower() or "таймер" in result.lower()

    def test_start_timer(self):
        reg = _make_registry()
        result = _run(reg.get("timer").handler(arg="start"))
        assert "▶️" in result or "запущен" in result.lower()

    def test_start_named_timer(self):
        reg = _make_registry()
        result = _run(reg.get("timer").handler(arg="start mytask"))
        assert "mytask" in result

    def test_timer_stored_in_memory(self):
        reg = _make_registry()
        _run(reg.get("timer").handler(arg="start work"))
        assert "work" in reg._timers

    def test_status_shows_elapsed(self):
        reg = _make_registry()
        _run(reg.get("timer").handler(arg="start work"))
        result = _run(reg.get("timer").handler(arg="status work"))
        assert "с" in result or "м" in result or "0" in result

    def test_stop_shows_elapsed(self):
        reg = _make_registry()
        _run(reg.get("timer").handler(arg="start work"))
        result = _run(reg.get("timer").handler(arg="stop work"))
        assert "⏹️" in result or "остановлен" in result.lower()

    def test_stop_removes_timer(self):
        reg = _make_registry()
        _run(reg.get("timer").handler(arg="start mytimer"))
        _run(reg.get("timer").handler(arg="stop mytimer"))
        assert "mytimer" not in reg._timers

    def test_list_shows_active(self):
        reg = _make_registry()
        _run(reg.get("timer").handler(arg="start alpha"))
        _run(reg.get("timer").handler(arg="start beta"))
        result = _run(reg.get("timer").handler(arg="list"))
        assert "alpha" in result
        assert "beta" in result

    def test_reset_restarts_timer(self):
        reg = _make_registry()
        _run(reg.get("timer").handler(arg="start work"))
        old_start = reg._timers.get("work")
        time.sleep(0.01)
        _run(reg.get("timer").handler(arg="reset work"))
        new_start = reg._timers.get("work")
        assert new_start is not None
        assert new_start >= old_start

    def test_clear_removes_all(self):
        reg = _make_registry()
        _run(reg.get("timer").handler(arg="start t1"))
        _run(reg.get("timer").handler(arg="start t2"))
        result = _run(reg.get("timer").handler(arg="clear"))
        assert len(reg._timers) == 0

    def test_double_start_shows_warning(self):
        reg = _make_registry()
        _run(reg.get("timer").handler(arg="start work"))
        result = _run(reg.get("timer").handler(arg="start work"))
        assert "уже" in result.lower() or "already" in result.lower()

    def test_stop_unknown_shows_warning(self):
        reg = _make_registry()
        result = _run(reg.get("timer").handler(arg="stop nonexistent_timer"))
        assert "не найден" in result or "not found" in result.lower()

    def test_status_unknown_shows_warning(self):
        reg = _make_registry()
        result = _run(reg.get("timer").handler(arg="status ghost_timer"))
        assert "не найден" in result or "not found" in result.lower()

    def test_lap_shows_elapsed(self):
        reg = _make_registry()
        _run(reg.get("timer").handler(arg="start coding"))
        result = _run(reg.get("timer").handler(arg="lap coding"))
        assert "coding" in result and ("с" in result or "lap" in result.lower())

    def test_default_timer_name(self):
        reg = _make_registry()
        _run(reg.get("timer").handler(arg="start"))
        assert "default" in reg._timers

    def test_elapsed_format(self):
        reg = _make_registry()
        _run(reg.get("timer").handler(arg="start t"))
        result = _run(reg.get("timer").handler(arg="status t"))
        import re
        assert re.search(r"\d+[счм]|[0-9]+s|0", result)

    def test_unknown_subcommand_shows_help(self):
        reg = _make_registry()
        result = _run(reg.get("timer").handler(arg="xyzzy_unknown"))
        assert "использование" in result.lower() or "start" in result.lower()
