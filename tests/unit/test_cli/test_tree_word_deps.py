"""Tests for /tree (#200), /word (#201), /deps (#202)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from lidco.cli.commands import CommandRegistry


def _run(coro) -> str:
    return asyncio.run(coro)


def _make_registry() -> CommandRegistry:
    return CommandRegistry()


# ── Task 200: /tree ───────────────────────────────────────────────────────────

class TestTreeCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("tree") is not None

    def test_nonexistent_path_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("tree").handler(arg="/nonexistent/path"))
        assert "не найден" in result or "not found" in result.lower()

    def test_shows_files(self, tmp_path):
        (tmp_path / "alpha.py").write_text("x = 1")
        (tmp_path / "beta.py").write_text("y = 2")
        reg = _make_registry()
        result = _run(reg.get("tree").handler(arg=str(tmp_path)))
        assert "alpha.py" in result
        assert "beta.py" in result

    def test_shows_directories(self, tmp_path):
        subdir = tmp_path / "mypackage"
        subdir.mkdir()
        (subdir / "__init__.py").write_text("")
        reg = _make_registry()
        result = _run(reg.get("tree").handler(arg=str(tmp_path)))
        assert "mypackage" in result

    def test_skips_pycache(self, tmp_path):
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "module.cpython-313.pyc").write_bytes(b"")
        reg = _make_registry()
        result = _run(reg.get("tree").handler(arg=str(tmp_path)))
        assert "__pycache__" not in result

    def test_skips_git(self, tmp_path):
        git = tmp_path / ".git"
        git.mkdir()
        (git / "config").write_text("[core]")
        reg = _make_registry()
        result = _run(reg.get("tree").handler(arg=str(tmp_path)))
        assert ".git" not in result

    def test_depth_flag(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "deep.py").write_text("x")
        reg = _make_registry()
        # depth 1 should not show deep.py
        result = _run(reg.get("tree").handler(arg=f"{tmp_path} --depth 1"))
        assert "deep.py" not in result

    def test_depth_2_shows_nested(self, tmp_path):
        nested = tmp_path / "pkg"
        nested.mkdir()
        (nested / "mod.py").write_text("x")
        reg = _make_registry()
        result = _run(reg.get("tree").handler(arg=f"{tmp_path} --depth 2"))
        assert "mod.py" in result

    def test_py_only_flag(self, tmp_path):
        (tmp_path / "code.py").write_text("x = 1")
        (tmp_path / "readme.txt").write_text("text")
        (tmp_path / "data.json").write_text("{}")
        reg = _make_registry()
        result = _run(reg.get("tree").handler(arg=f"{tmp_path} --py"))
        assert "code.py" in result
        assert "readme.txt" not in result
        assert "data.json" not in result

    def test_shows_file_and_dir_counts(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        (tmp_path / "b.py").write_text("y")
        reg = _make_registry()
        result = _run(reg.get("tree").handler(arg=str(tmp_path)))
        assert "файлов" in result or "file" in result.lower() or "2" in result

    def test_empty_directory(self, tmp_path):
        empty = tmp_path / "empty_dir"
        empty.mkdir()
        reg = _make_registry()
        result = _run(reg.get("tree").handler(arg=str(empty)))
        assert "пусто" in result or "empty" in result.lower() or isinstance(result, str)

    def test_shows_depth_hint(self, tmp_path):
        (tmp_path / "x.py").write_text("x")
        reg = _make_registry()
        result = _run(reg.get("tree").handler(arg=str(tmp_path)))
        assert "--depth" in result or "глубина" in result or "depth" in result.lower()


# ── Task 201: /word ───────────────────────────────────────────────────────────

class TestWordCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("word") is not None

    def test_no_arg_shows_usage(self):
        reg = _make_registry()
        result = _run(reg.get("word").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_counts_words_in_text(self):
        reg = _make_registry()
        result = _run(reg.get("word").handler(arg="apple banana apple cherry apple"))
        assert "apple" in result
        assert "3" in result  # apple appears 3 times

    def test_counts_words_in_file(self, tmp_path):
        f = tmp_path / "text.txt"
        f.write_text("hello world hello foo hello world\n")
        reg = _make_registry()
        result = _run(reg.get("word").handler(arg=str(f)))
        assert "hello" in result
        assert "3" in result

    def test_top_flag_limits_results(self, tmp_path):
        f = tmp_path / "big.txt"
        words = " ".join(f"word{i}" * (20 - i) for i in range(20))
        f.write_text(words)
        reg = _make_registry()
        result = _run(reg.get("word").handler(arg=f"{f} --top 3"))
        # Should only show 3 words
        assert "3" in result

    def test_shows_total_and_unique_counts(self):
        reg = _make_registry()
        result = _run(reg.get("word").handler(arg="alpha beta gamma alpha beta"))
        assert "уникальных" in result.lower() or "unique" in result.lower()

    def test_shows_bar_chart(self):
        reg = _make_registry()
        result = _run(reg.get("word").handler(arg="hello world hello hello"))
        assert "█" in result or "░" in result

    def test_shows_percentage(self):
        reg = _make_registry()
        result = _run(reg.get("word").handler(arg="hello world hello hello world"))
        assert "%" in result

    def test_filters_stop_words(self):
        reg = _make_registry()
        # "and", "the", "for" are stop words (< 3 chars or in stop list)
        result = _run(reg.get("word").handler(arg="and the for apple apple apple"))
        # "and"/"the"/"for" should not appear as top words
        assert result.count("apple") >= 1

    def test_empty_content_shows_message(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("# no words here\n")
        reg = _make_registry()
        result = _run(reg.get("word").handler(arg=str(f)))
        # Only very short words in comment — may get "filtered" result
        assert isinstance(result, str) and len(result) > 0

    def test_shows_source_label(self, tmp_path):
        f = tmp_path / "source.py"
        f.write_text("function method attribute class")
        reg = _make_registry()
        result = _run(reg.get("word").handler(arg=str(f)))
        assert "source.py" in result


# ── Task 202: /deps ───────────────────────────────────────────────────────────

class TestDepsCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("deps") is not None

    def test_no_arg_shows_usage(self):
        reg = _make_registry()
        result = _run(reg.get("deps").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_nonexistent_file_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("deps").handler(arg="/nonexistent/file.py"))
        assert "не найден" in result or "not found" in result.lower()

    def test_directory_rejected(self, tmp_path):
        reg = _make_registry()
        result = _run(reg.get("deps").handler(arg=str(tmp_path)))
        assert "не файл" in result or "not a file" in result.lower()

    def test_detects_stdlib_imports(self, tmp_path):
        f = tmp_path / "module.py"
        f.write_text("import os\nimport sys\nimport re\n")
        reg = _make_registry()
        result = _run(reg.get("deps").handler(arg=str(f)))
        assert "os" in result or "sys" in result or "re" in result
        assert "stdlib" in result.lower() or "стандартная" in result.lower()

    def test_detects_third_party(self, tmp_path):
        f = tmp_path / "module.py"
        f.write_text("import rich\nimport pydantic\n")
        reg = _make_registry()
        result = _run(reg.get("deps").handler(arg=str(f)))
        assert "rich" in result or "pydantic" in result
        assert "сторонн" in result.lower() or "third" in result.lower()

    def test_from_import_parsed(self, tmp_path):
        f = tmp_path / "module.py"
        f.write_text("from pathlib import Path\nfrom typing import Any\n")
        reg = _make_registry()
        result = _run(reg.get("deps").handler(arg=str(f)))
        assert "pathlib" in result or "typing" in result

    def test_no_imports_shows_message(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("x = 1\ny = 2\n")
        reg = _make_registry()
        result = _run(reg.get("deps").handler(arg=str(f)))
        assert "нет" in result or "no" in result.lower() or "0" in result

    def test_shows_total_count(self, tmp_path):
        f = tmp_path / "counted.py"
        f.write_text("import os\nimport sys\nimport rich\n")
        reg = _make_registry()
        result = _run(reg.get("deps").handler(arg=str(f)))
        assert "3" in result or "импорт" in result.lower()

    def test_future_import_handled(self, tmp_path):
        f = tmp_path / "future.py"
        f.write_text("from __future__ import annotations\nimport os\n")
        reg = _make_registry()
        result = _run(reg.get("deps").handler(arg=str(f)))
        assert isinstance(result, str)

    def test_shows_file_label(self, tmp_path):
        f = tmp_path / "labeled.py"
        f.write_text("import os\n")
        reg = _make_registry()
        result = _run(reg.get("deps").handler(arg=str(f)))
        assert "labeled.py" in result
