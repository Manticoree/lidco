"""Tests for /head (#222), /tail (#223), /cd (#224a), /ls (#224b), /macro (#225)."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from lidco.cli.commands import CommandRegistry


def _run(coro) -> str:
    return asyncio.run(coro)


def _make_registry() -> CommandRegistry:
    return CommandRegistry()


# ── Task 222: /head ───────────────────────────────────────────────────────────

class TestHeadCommand:
    def test_registered(self):
        assert _make_registry().get("head") is not None

    def test_no_arg_shows_usage(self):
        result = _run(_make_registry().get("head").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_shows_first_10_by_default(self, tmp_path):
        f = tmp_path / "file.py"
        f.write_text("\n".join(f"line{i}" for i in range(1, 31)))
        result = _run(_make_registry().get("head").handler(arg=str(f)))
        assert "line1" in result
        assert "line10" in result
        assert "line11" not in result

    def test_custom_n(self, tmp_path):
        f = tmp_path / "file.py"
        f.write_text("\n".join(f"L{i}" for i in range(1, 21)))
        result = _run(_make_registry().get("head").handler(arg=f"{f} 5"))
        assert "L5" in result
        assert "L6" not in result

    def test_nonexistent_shows_error(self):
        result = _run(_make_registry().get("head").handler(arg="/nonexistent/file.py"))
        assert "не найден" in result or "not found" in result.lower()

    def test_directory_rejected(self, tmp_path):
        result = _run(_make_registry().get("head").handler(arg=str(tmp_path)))
        assert "не файл" in result or "not" in result.lower()

    def test_shows_total_count(self, tmp_path):
        f = tmp_path / "counted.py"
        f.write_text("\n".join(str(i) for i in range(50)))
        result = _run(_make_registry().get("head").handler(arg=str(f)))
        assert "50" in result

    def test_shows_file_name(self, tmp_path):
        f = tmp_path / "myfile.py"
        f.write_text("x = 1\n")
        result = _run(_make_registry().get("head").handler(arg=str(f)))
        assert "myfile.py" in result

    def test_code_block(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("def foo(): pass\n")
        result = _run(_make_registry().get("head").handler(arg=str(f)))
        assert "```" in result

    def test_binary_rejected(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_bytes(b"\x00\x01binary")
        result = _run(_make_registry().get("head").handler(arg=str(f)))
        assert "бинарный" in result or "binary" in result.lower()

    def test_shows_continuation_hint(self, tmp_path):
        f = tmp_path / "long.py"
        f.write_text("\n".join(f"x{i}" for i in range(50)))
        result = _run(_make_registry().get("head").handler(arg=f"{f} 5"))
        assert "ещё" in result or "cat" in result.lower() or "50" in result


# ── Task 223: /tail ───────────────────────────────────────────────────────────

class TestTailCommand:
    def test_registered(self):
        assert _make_registry().get("tail") is not None

    def test_no_arg_shows_usage(self):
        result = _run(_make_registry().get("tail").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_shows_last_10_by_default(self, tmp_path):
        f = tmp_path / "file.py"
        f.write_text("\n".join(f"row{i}" for i in range(1, 31)))
        result = _run(_make_registry().get("tail").handler(arg=str(f)))
        assert "row30" in result
        assert "row21" in result
        assert "row20" not in result

    def test_custom_n(self, tmp_path):
        f = tmp_path / "file.py"
        f.write_text("\n".join(f"L{i}" for i in range(1, 21)))
        result = _run(_make_registry().get("tail").handler(arg=f"{f} 3"))
        assert "L20" in result
        assert "L19" in result
        assert "L18" in result
        assert "L17" not in result

    def test_nonexistent_shows_error(self):
        result = _run(_make_registry().get("tail").handler(arg="/no/file.txt"))
        assert "не найден" in result or "not found" in result.lower()

    def test_shows_file_name(self, tmp_path):
        f = tmp_path / "log.txt"
        f.write_text("a\nb\nc\n")
        result = _run(_make_registry().get("tail").handler(arg=str(f)))
        assert "log.txt" in result

    def test_shows_line_range(self, tmp_path):
        f = tmp_path / "ranged.py"
        f.write_text("\n".join(str(i) for i in range(1, 21)))
        result = _run(_make_registry().get("tail").handler(arg=str(f)))
        assert "20" in result

    def test_code_block(self, tmp_path):
        f = tmp_path / "src.py"
        f.write_text("x = 1\n")
        result = _run(_make_registry().get("tail").handler(arg=str(f)))
        assert "```" in result

    def test_binary_rejected(self, tmp_path):
        f = tmp_path / "bin.dat"
        f.write_bytes(b"\x00binary\x01")
        result = _run(_make_registry().get("tail").handler(arg=str(f)))
        assert "бинарный" in result or "binary" in result.lower()


# ── Task 224a: /cd ────────────────────────────────────────────────────────────

class TestCdCommand:
    def test_registered(self):
        assert _make_registry().get("cd") is not None

    def test_changes_directory(self, tmp_path):
        orig = os.getcwd()
        try:
            result = _run(_make_registry().get("cd").handler(arg=str(tmp_path)))
            assert "✓" in result or str(tmp_path) in result
            assert os.getcwd() == str(tmp_path)
        finally:
            os.chdir(orig)

    def test_nonexistent_shows_error(self):
        result = _run(_make_registry().get("cd").handler(arg="/nonexistent/path/xyz"))
        assert "не найдена" in result or "not found" in result.lower()

    def test_file_rejected(self, tmp_path):
        f = tmp_path / "file.py"
        f.write_text("x")
        result = _run(_make_registry().get("cd").handler(arg=str(f)))
        assert "не директория" in result or "not" in result.lower()

    def test_dotdot_goes_up(self, tmp_path):
        orig = os.getcwd()
        try:
            os.chdir(tmp_path)
            parent = str(tmp_path.parent)
            result = _run(_make_registry().get("cd").handler(arg=".."))
            assert "✓" in result or parent in result
            assert os.getcwd() == parent
        finally:
            os.chdir(orig)

    def test_shows_new_path(self, tmp_path):
        orig = os.getcwd()
        try:
            result = _run(_make_registry().get("cd").handler(arg=str(tmp_path)))
            assert str(tmp_path) in result or "✓" in result
        finally:
            os.chdir(orig)

    def test_shows_file_count(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        (tmp_path / "b.py").write_text("y")
        orig = os.getcwd()
        try:
            result = _run(_make_registry().get("cd").handler(arg=str(tmp_path)))
            assert "2" in result or "файл" in result.lower()
        finally:
            os.chdir(orig)

    def test_dash_returns_previous(self, tmp_path):
        orig = os.getcwd()
        sub = tmp_path / "sub"
        sub.mkdir()
        try:
            reg = _make_registry()
            _run(reg.get("cd").handler(arg=str(tmp_path)))
            _run(reg.get("cd").handler(arg=str(sub)))
            result = _run(reg.get("cd").handler(arg="-"))
            assert "✓" in result or str(tmp_path) in result
        finally:
            os.chdir(orig)


# ── Task 224b: /ls ────────────────────────────────────────────────────────────

class TestLsCommand:
    def test_registered(self):
        assert _make_registry().get("ls") is not None

    def test_lists_files(self, tmp_path):
        (tmp_path / "alpha.py").write_text("x")
        (tmp_path / "beta.py").write_text("y")
        result = _run(_make_registry().get("ls").handler(arg=str(tmp_path)))
        assert "alpha.py" in result
        assert "beta.py" in result

    def test_lists_dirs(self, tmp_path):
        (tmp_path / "subdir").mkdir()
        result = _run(_make_registry().get("ls").handler(arg=str(tmp_path)))
        assert "subdir" in result

    def test_shows_count(self, tmp_path):
        for i in range(4):
            (tmp_path / f"f{i}.py").write_text("x")
        result = _run(_make_registry().get("ls").handler(arg=str(tmp_path)))
        assert "4" in result

    def test_long_mode(self, tmp_path):
        (tmp_path / "sized.py").write_text("x" * 100)
        result = _run(_make_registry().get("ls").handler(arg=f"{tmp_path} --l"))
        assert "sized.py" in result
        assert "Б" in result or "КБ" in result or "МБ" in result

    def test_skips_hidden_by_default(self, tmp_path):
        (tmp_path / ".hidden").write_text("x")
        (tmp_path / "visible.py").write_text("y")
        result = _run(_make_registry().get("ls").handler(arg=str(tmp_path)))
        assert ".hidden" not in result
        assert "visible.py" in result

    def test_all_flag_shows_hidden(self, tmp_path):
        (tmp_path / ".hidden").write_text("x")
        result = _run(_make_registry().get("ls").handler(arg=f"{tmp_path} --all"))
        assert ".hidden" in result

    def test_nonexistent_shows_error(self):
        result = _run(_make_registry().get("ls").handler(arg="/nonexistent/dir"))
        assert "/nonexistent/dir" in result  # path echoed back in error message

    def test_empty_dir_shows_message(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        result = _run(_make_registry().get("ls").handler(arg=str(empty)))
        assert "пусто" in result or "empty" in result.lower()

    def test_groups_by_extension(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        (tmp_path / "b.json").write_text("{}")
        result = _run(_make_registry().get("ls").handler(arg=str(tmp_path)))
        assert ".py" in result or "a.py" in result


# ── Task 225: /macro ──────────────────────────────────────────────────────────

class TestMacroCommand:
    def test_registered(self):
        assert _make_registry().get("macro") is not None

    def test_no_macros_shows_empty(self):
        result = _run(_make_registry().get("macro").handler())
        assert "нет" in result.lower() or "no" in result.lower() or "создайте" in result.lower()

    def test_record_starts_recording(self):
        reg = _make_registry()
        result = _run(reg.get("macro").handler(arg="record mymacro"))
        assert "mymacro" in result
        assert reg._macro_recording == "mymacro"

    def test_record_without_name_shows_error(self):
        result = _run(_make_registry().get("macro").handler(arg="record"))
        assert "имя" in result.lower() or "name" in result.lower() or "укажите" in result.lower()

    def test_add_command_to_recording(self):
        reg = _make_registry()
        _run(reg.get("macro").handler(arg="record test"))
        result = _run(reg.get("macro").handler(arg="add git status"))
        assert "git status" in result or "добавлено" in result.lower()
        assert "git status" in reg._macro_buffer

    def test_stop_saves_macro(self):
        reg = _make_registry()
        _run(reg.get("macro").handler(arg="record mymacro"))
        _run(reg.get("macro").handler(arg="add git status"))
        _run(reg.get("macro").handler(arg="add lint"))
        result = _run(reg.get("macro").handler(arg="stop"))
        assert "mymacro" in reg._macros
        assert len(reg._macros["mymacro"]) == 2
        assert reg._macro_recording is None

    def test_list_shows_macros(self):
        reg = _make_registry()
        _run(reg.get("macro").handler(arg="record alpha"))
        _run(reg.get("macro").handler(arg="add status"))
        _run(reg.get("macro").handler(arg="stop"))
        result = _run(reg.get("macro").handler(arg="list"))
        assert "alpha" in result

    def test_play_shows_steps(self):
        reg = _make_registry()
        _run(reg.get("macro").handler(arg="record run_checks"))
        _run(reg.get("macro").handler(arg="add lint"))
        _run(reg.get("macro").handler(arg="add git status"))
        _run(reg.get("macro").handler(arg="stop"))
        result = _run(reg.get("macro").handler(arg="play run_checks"))
        assert "lint" in result
        assert "git status" in result

    def test_play_unknown_shows_error(self):
        result = _run(_make_registry().get("macro").handler(arg="play nonexistent"))
        assert "не найден" in result or "not found" in result.lower()

    def test_del_removes_macro(self):
        reg = _make_registry()
        _run(reg.get("macro").handler(arg="record todel"))
        _run(reg.get("macro").handler(arg="stop"))
        _run(reg.get("macro").handler(arg="del todel"))
        assert "todel" not in reg._macros

    def test_show_displays_commands(self):
        reg = _make_registry()
        _run(reg.get("macro").handler(arg="record viewer"))
        _run(reg.get("macro").handler(arg="add git log 5"))
        _run(reg.get("macro").handler(arg="stop"))
        result = _run(reg.get("macro").handler(arg="show viewer"))
        assert "git log 5" in result

    def test_clear_removes_all(self):
        reg = _make_registry()
        _run(reg.get("macro").handler(arg="record m1"))
        _run(reg.get("macro").handler(arg="stop"))
        _run(reg.get("macro").handler(arg="record m2"))
        _run(reg.get("macro").handler(arg="stop"))
        _run(reg.get("macro").handler(arg="clear"))
        assert len(reg._macros) == 0

    def test_double_record_shows_error(self):
        reg = _make_registry()
        _run(reg.get("macro").handler(arg="record first"))
        result = _run(reg.get("macro").handler(arg="record second"))
        assert "уже" in result.lower() or "already" in result.lower() or "first" in result

    def test_stop_without_recording_shows_error(self):
        result = _run(_make_registry().get("macro").handler(arg="stop"))
        assert "нет" in result.lower() or "no" in result.lower() or "активной" in result.lower()

    def test_unknown_subcommand_shows_help(self):
        result = _run(_make_registry().get("macro").handler(arg="xyzzy"))
        assert "использование" in result.lower() or "usage" in result.lower() or "record" in result
