"""Tests for SymbolRenamer (T532)."""
from __future__ import annotations
import textwrap
from pathlib import Path
import pytest
from lidco.refactor.symbol_rename import SymbolRenamer, RenameOccurrence, RenameResult


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


def test_find_occurrences_basic(tmp_path):
    _write(tmp_path, "a.py", "def my_func(): pass\nmy_func()\n")
    r = SymbolRenamer(tmp_path)
    occ = r.find_occurrences("my_func")
    assert len(occ) == 2


def test_find_occurrences_no_match(tmp_path):
    _write(tmp_path, "a.py", "x = 1\n")
    r = SymbolRenamer(tmp_path)
    assert r.find_occurrences("missing") == []


def test_find_occurrences_word_boundary(tmp_path):
    _write(tmp_path, "a.py", "my_func_extra = 1\nmy_func = 2\n")
    r = SymbolRenamer(tmp_path)
    occ = r.find_occurrences("my_func")
    names = [o.context.strip() for o in occ]
    assert any("my_func = 2" in n for n in names)


def test_rename_basic(tmp_path):
    _write(tmp_path, "a.py", "def old_name(): pass\nold_name()\n")
    r = SymbolRenamer(tmp_path)
    result = r.rename("old_name", "new_name")
    assert result.files_changed == 1
    assert result.occurrences == 2
    content = (tmp_path / "a.py").read_text()
    assert "new_name" in content
    assert "old_name" not in content


def test_rename_dry_run(tmp_path):
    _write(tmp_path, "a.py", "def old(): pass\n")
    r = SymbolRenamer(tmp_path)
    result = r.rename("old", "new_fn", dry_run=True)
    assert result.files_changed == 1
    # File not actually changed
    assert "old" in (tmp_path / "a.py").read_text()


def test_rename_multiple_files(tmp_path):
    _write(tmp_path, "a.py", "foo = 1\n")
    _write(tmp_path, "b.py", "foo = 2\n")
    r = SymbolRenamer(tmp_path)
    result = r.rename("foo", "bar")
    assert result.files_changed == 2


def test_rename_result_preview(tmp_path):
    _write(tmp_path, "x.py", "thing = 1\n")
    r = SymbolRenamer(tmp_path)
    result = r.rename("thing", "other")
    assert len(result.preview) == 1


def test_rename_no_occurrences(tmp_path):
    _write(tmp_path, "a.py", "x = 1\n")
    r = SymbolRenamer(tmp_path)
    result = r.rename("nonexistent", "something")
    assert result.files_changed == 0
    assert result.occurrences == 0


def test_occurrence_has_line_and_column(tmp_path):
    _write(tmp_path, "a.py", "x = 1\nfoo = 2\n")
    r = SymbolRenamer(tmp_path)
    occ = r.find_occurrences("foo")
    assert occ[0].line == 2
    assert occ[0].column == 0
