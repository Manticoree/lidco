"""Tests for TestGenerator (T534)."""
from __future__ import annotations
import textwrap
from pathlib import Path
import pytest
from lidco.scaffold.test_gen import TestGenerator, GeneratedTests, _extract_functions


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


def test_extract_functions_basic():
    source = "def foo(x, y): pass\ndef bar(): pass\n"
    funcs = _extract_functions(source)
    names = [f.name for f in funcs]
    assert "foo" in names
    assert "bar" in names


def test_extract_functions_skips_private():
    source = "def _private(): pass\ndef public(): pass\n"
    funcs = _extract_functions(source)
    names = [f.name for f in funcs]
    assert "_private" not in names
    assert "public" in names


def test_extract_async_function():
    source = "async def fetch(url): pass\n"
    funcs = _extract_functions(source)
    assert funcs[0].is_async is True
    assert funcs[0].name == "fetch"


def test_generate_for_module(tmp_path):
    p = _write(tmp_path, "mod.py", "def add(a, b):\n    return a + b\n")
    gen = TestGenerator()
    result = gen.generate_for_module(str(p))
    assert result.error == ""
    assert "add" in result.functions_covered
    assert "test_add" in result.test_code


def test_generate_for_module_file_not_found():
    gen = TestGenerator()
    result = gen.generate_for_module("/nonexistent/path.py")
    assert result.error != ""
    assert result.test_code == ""


def test_generate_no_public_functions(tmp_path):
    p = _write(tmp_path, "mod.py", "def _internal(): pass\n")
    gen = TestGenerator()
    result = gen.generate_for_module(str(p))
    assert result.functions_covered == []


def test_write_test_file(tmp_path):
    gen = TestGenerator()
    out = tmp_path / "subdir" / "test_mod.py"
    gen.write_test_file("# test\n", str(out))
    assert out.exists()
    assert out.read_text() == "# test\n"


def test_generate_async_no_llm(tmp_path):
    import asyncio
    p = _write(tmp_path, "mod.py", "def greet(name): return name\n")
    gen = TestGenerator()
    result = asyncio.run(gen.generate_async(str(p)))
    assert "greet" in result.functions_covered
