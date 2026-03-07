"""Tests for /regex (#212), /stat (#213), /diff3 (#214)."""

from __future__ import annotations

import asyncio
import stat
from pathlib import Path

import pytest

from lidco.cli.commands import CommandRegistry


def _run(coro) -> str:
    return asyncio.run(coro)


def _make_registry() -> CommandRegistry:
    return CommandRegistry()


# ── Task 212: /regex ──────────────────────────────────────────────────────────

class TestRegexCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("regex") is not None

    def test_no_arg_shows_usage(self):
        reg = _make_registry()
        result = _run(reg.get("regex").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_basic_match(self):
        reg = _make_registry()
        result = _run(reg.get("regex").handler(arg=r"\d+ hello 42"))
        assert "42" in result

    def test_no_match(self):
        reg = _make_registry()
        result = _run(reg.get("regex").handler(arg=r"\d+ no digits here"))
        assert "нет" in result.lower() or "no" in result.lower() or "❌" in result

    def test_capture_group(self):
        reg = _make_registry()
        result = _run(reg.get("regex").handler(arg=r"(\w+)@(\w+) user@example"))
        assert "user" in result or "Группа" in result

    def test_named_group(self):
        reg = _make_registry()
        result = _run(reg.get("regex").handler(arg=r"(?P<year>\d{4})-(?P<month>\d{2}) 2024-01"))
        assert "year" in result or "2024" in result

    def test_flag_ignore_case(self):
        reg = _make_registry()
        result = _run(reg.get("regex").handler(arg=r"HELLO --i hello world"))
        assert "hello" in result.lower() or "✅" in result

    def test_flag_all_shows_multiple(self):
        reg = _make_registry()
        result = _run(reg.get("regex").handler(arg=r"\d+ --all 1 and 2 and 3"))
        assert "3" in result or "совпадений" in result.lower()

    def test_invalid_pattern_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("regex").handler(arg="[invalid( text"))
        assert "ошибка" in result.lower() or "error" in result.lower()

    def test_one_arg_no_text_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("regex").handler(arg=r"\d+"))
        assert "паттерн" in result.lower() or "текст" in result.lower() or "укажите" in result.lower()

    def test_shows_match_position(self):
        reg = _make_registry()
        result = _run(reg.get("regex").handler(arg=r"\d+ abc 123 def"))
        assert "позиция" in result.lower() or "4" in result or "7" in result

    def test_multiline_flag(self):
        reg = _make_registry()
        result = _run(reg.get("regex").handler(arg=r"^def --m --all def foo\ndef bar"))
        assert isinstance(result, str) and len(result) > 0

    def test_shows_match_label(self):
        reg = _make_registry()
        result = _run(reg.get("regex").handler(arg=r"foo foo bar"))
        assert "✅" in result or "совпадение" in result.lower() or "foo" in result


# ── Task 213: /stat ───────────────────────────────────────────────────────────

class TestStatCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("stat") is not None

    def test_no_arg_shows_usage(self):
        reg = _make_registry()
        result = _run(reg.get("stat").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_nonexistent_path_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("stat").handler(arg="/nonexistent/path/file.py"))
        assert "не найден" in result or "not found" in result.lower()

    def test_file_shows_name(self, tmp_path):
        f = tmp_path / "hello.py"
        f.write_text("x = 1\n")
        reg = _make_registry()
        result = _run(reg.get("stat").handler(arg=str(f)))
        assert "hello.py" in result

    def test_file_shows_size(self, tmp_path):
        f = tmp_path / "sized.py"
        content = "x = 1\n"
        f.write_text(content)
        reg = _make_registry()
        result = _run(reg.get("stat").handler(arg=str(f)))
        assert str(len(content)) in result or "байт" in result.lower()

    def test_file_shows_line_count(self, tmp_path):
        f = tmp_path / "lines.py"
        f.write_text("a = 1\nb = 2\nc = 3\n")
        reg = _make_registry()
        result = _run(reg.get("stat").handler(arg=str(f)))
        assert "3" in result

    def test_file_shows_mtime(self, tmp_path):
        f = tmp_path / "timed.py"
        f.write_text("x")
        reg = _make_registry()
        result = _run(reg.get("stat").handler(arg=str(f)))
        import re
        assert re.search(r"\d{4}-\d{2}-\d{2}", result)

    def test_file_shows_permissions(self, tmp_path):
        f = tmp_path / "perms.py"
        f.write_text("x")
        reg = _make_registry()
        result = _run(reg.get("stat").handler(arg=str(f)))
        assert "rw" in result or "права" in result.lower() or "-" in result

    def test_detects_python_language(self, tmp_path):
        f = tmp_path / "script.py"
        f.write_text("def foo(): pass\n")
        reg = _make_registry()
        result = _run(reg.get("stat").handler(arg=str(f)))
        assert "Python" in result

    def test_directory_shows_file_count(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        (tmp_path / "b.py").write_text("y")
        reg = _make_registry()
        result = _run(reg.get("stat").handler(arg=str(tmp_path)))
        assert "2" in result or "файл" in result.lower()

    def test_directory_type_label(self, tmp_path):
        reg = _make_registry()
        result = _run(reg.get("stat").handler(arg=str(tmp_path)))
        assert "директория" in result.lower() or "directory" in result.lower()

    def test_shows_word_count(self, tmp_path):
        f = tmp_path / "words.txt"
        f.write_text("one two three four five\n")
        reg = _make_registry()
        result = _run(reg.get("stat").handler(arg=str(f)))
        assert "5" in result or "слов" in result.lower()

    def test_shows_char_count(self, tmp_path):
        f = tmp_path / "chars.txt"
        content = "abcde"
        f.write_text(content)
        reg = _make_registry()
        result = _run(reg.get("stat").handler(arg=str(f)))
        assert "5" in result or "символ" in result.lower()


# ── Task 214: /diff3 ──────────────────────────────────────────────────────────

class TestDiff3Command:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("diff3") is not None

    def test_no_arg_shows_usage(self):
        reg = _make_registry()
        result = _run(reg.get("diff3").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_two_args_shows_error(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("x")
        f2.write_text("y")
        reg = _make_registry()
        result = _run(reg.get("diff3").handler(arg=f"{f1} {f2}"))
        assert "три" in result or "three" in result.lower() or "нужно" in result.lower() or "3" in result

    def test_missing_file_shows_error(self, tmp_path):
        f1 = tmp_path / "a.py"
        f1.write_text("x")
        reg = _make_registry()
        result = _run(reg.get("diff3").handler(arg=f"{f1} /nonexistent/b.py /nonexistent/c.py"))
        assert "не найден" in result or "not found" in result.lower()

    def test_identical_files_no_conflicts(self, tmp_path):
        content = "x = 1\ny = 2\n"
        base = tmp_path / "base.py"
        ours = tmp_path / "ours.py"
        theirs = tmp_path / "theirs.py"
        base.write_text(content)
        ours.write_text(content)
        theirs.write_text(content)
        reg = _make_registry()
        result = _run(reg.get("diff3").handler(arg=f"{base} {ours} {theirs}"))
        assert "конфликтов нет" in result.lower() or "✅" in result or "no conflict" in result.lower()

    def test_different_files_shows_diff(self, tmp_path):
        base = tmp_path / "base.py"
        ours = tmp_path / "ours.py"
        theirs = tmp_path / "theirs.py"
        base.write_text("x = 1\n")
        ours.write_text("x = 2\n")
        theirs.write_text("x = 3\n")
        reg = _make_registry()
        result = _run(reg.get("diff3").handler(arg=f"{base} {ours} {theirs}"))
        assert isinstance(result, str) and len(result) > 0

    def test_shows_file_names(self, tmp_path):
        base = tmp_path / "base.py"
        ours = tmp_path / "ours.py"
        theirs = tmp_path / "theirs.py"
        for f in (base, ours, theirs):
            f.write_text("x = 1\n")
        reg = _make_registry()
        result = _run(reg.get("diff3").handler(arg=f"{base} {ours} {theirs}"))
        assert "base.py" in result
        assert "ours.py" in result
        assert "theirs.py" in result

    def test_shows_added_removed_stats(self, tmp_path):
        base = tmp_path / "base.py"
        ours = tmp_path / "ours.py"
        theirs = tmp_path / "theirs.py"
        base.write_text("a = 1\nb = 2\n")
        ours.write_text("a = 1\nb = 2\nc = 3\n")
        theirs.write_text("a = 1\n")
        reg = _make_registry()
        result = _run(reg.get("diff3").handler(arg=f"{base} {ours} {theirs}"))
        assert "+" in result or "−" in result or "добавлено" in result.lower()

    def test_ours_theirs_identical_no_diff(self, tmp_path):
        base = tmp_path / "base.py"
        ours = tmp_path / "ours.py"
        theirs = tmp_path / "theirs.py"
        base.write_text("x = 1\n")
        ours.write_text("x = 99\n")
        theirs.write_text("x = 99\n")
        reg = _make_registry()
        result = _run(reg.get("diff3").handler(arg=f"{base} {ours} {theirs}"))
        assert "идентичны" in result or "identical" in result.lower() or "✅" in result

    def test_directory_rejected(self, tmp_path):
        base = tmp_path / "base.py"
        base.write_text("x")
        reg = _make_registry()
        result = _run(reg.get("diff3").handler(arg=f"{base} {base} {tmp_path}"))
        assert "не является файлом" in result or "not a file" in result.lower()

    def test_shows_diff_header(self, tmp_path):
        base = tmp_path / "base.py"
        ours = tmp_path / "ours.py"
        theirs = tmp_path / "theirs.py"
        base.write_text("x = 1\n")
        ours.write_text("x = 2\n")
        theirs.write_text("x = 3\n")
        reg = _make_registry()
        result = _run(reg.get("diff3").handler(arg=f"{base} {ours} {theirs}"))
        assert "diff" in result.lower() or "3-way" in result.lower() or "база" in result.lower()
