"""Tests for CodeExplainer (T563)."""
from __future__ import annotations
import asyncio
from pathlib import Path
import pytest
from lidco.analysis.code_explainer import CodeExplainer, CodeExplanation


SOURCE = '''
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
'''


def test_explain_function_basic():
    e = CodeExplainer()
    exp = e.explain_function(SOURCE, "add")
    assert exp.subject == "add"
    assert exp.complexity in ("low", "medium", "high")


def test_explain_function_docstring():
    e = CodeExplainer()
    exp = e.explain_function(SOURCE, "add")
    sections = {s.title: s.body for s in exp.sections}
    assert "Add two numbers" in sections.get("Docstring", "")


def test_explain_function_not_found():
    e = CodeExplainer()
    exp = e.explain_function(SOURCE, "missing")
    assert "not found" in exp.sections[0].body.lower()


def test_explain_file(tmp_path):
    p = tmp_path / "mod.py"
    p.write_text('"""Module doc."""\ndef foo(): pass\n', encoding="utf-8")
    e = CodeExplainer()
    exp = e.explain_file(str(p))
    assert exp.subject == "mod.py"
    assert any("foo" in s.body for s in exp.sections)


def test_explain_file_not_found():
    e = CodeExplainer()
    exp = e.explain_file("/no/such/file.py")
    assert "Error" in exp.sections[0].title


def test_format_output():
    e = CodeExplainer()
    exp = e.explain_function(SOURCE, "add")
    fmt = exp.format()
    assert "add" in fmt
    assert "##" in fmt


def test_explain_async_no_llm():
    e = CodeExplainer()
    exp = asyncio.run(e.explain_async(SOURCE, "add"))
    assert exp.subject == "add"


def test_complexity_estimate():
    deep = '''
def deep():
    if True:
        for i in range(10):
            while True:
                if i:
                    if i > 5:
                        pass
'''
    e = CodeExplainer()
    exp = e.explain_function(deep, "deep")
    assert exp.complexity in ("medium", "high")
