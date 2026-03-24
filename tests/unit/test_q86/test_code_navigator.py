"""Tests for CodeNavigator (T562)."""
from __future__ import annotations
import textwrap
from pathlib import Path
import pytest
from lidco.navigation.code_navigator import CodeNavigator, SymbolLocation


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


def test_find_definition(tmp_path):
    _write(tmp_path, "mod.py", "def my_func():\n    pass\n")
    nav = CodeNavigator(tmp_path)
    result = nav.find("my_func")
    assert len(result.definitions) == 1
    assert result.definitions[0].kind == "def"


def test_find_references(tmp_path):
    _write(tmp_path, "mod.py", "def foo():\n    pass\n")
    _write(tmp_path, "use.py", "from mod import foo\nfoo()\n")
    nav = CodeNavigator(tmp_path)
    result = nav.find("foo")
    assert result.total > 0


def test_find_no_results(tmp_path):
    _write(tmp_path, "mod.py", "x = 1\n")
    nav = CodeNavigator(tmp_path)
    result = nav.find("nonexistent_symbol")
    assert result.total == 0


def test_callers(tmp_path):
    _write(tmp_path, "mod.py", "def bar(): pass\ndef caller():\n    bar()\n")
    nav = CodeNavigator(tmp_path)
    callers = nav.callers("bar")
    assert len(callers) >= 1


def test_symbols_in_file(tmp_path):
    p = _write(tmp_path, "mod.py", "class Foo:\n    pass\ndef baz():\n    pass\n")
    nav = CodeNavigator(tmp_path)
    symbols = nav.symbols_in_file(str(p))
    kinds = {s.kind for s in symbols}
    assert "class" in kinds
    assert "def" in kinds


def test_format_summary(tmp_path):
    _write(tmp_path, "mod.py", "def alpha(): pass\nalpha()\n")
    nav = CodeNavigator(tmp_path)
    result = nav.find("alpha")
    summary = result.format_summary()
    assert "alpha" in summary


def test_symbols_in_nonexistent_file(tmp_path):
    nav = CodeNavigator(tmp_path)
    assert nav.symbols_in_file("/nonexistent/file.py") == []
