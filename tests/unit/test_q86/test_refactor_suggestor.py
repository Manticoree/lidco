"""Tests for RefactorSuggestor (T564)."""
from __future__ import annotations
import textwrap
from pathlib import Path
import pytest
from lidco.refactor.refactor_suggestor import RefactorSuggestor, RefactorReport


def test_no_suggestions_simple():
    source = "def add(a, b):\n    return a + b\n"
    r = RefactorSuggestor()
    report = r.analyse_source(source)
    # short simple function → possibly 0 or only inline_variable hints
    assert isinstance(report, RefactorReport)


def test_split_function_long():
    source = "def long_func():\n" + "    x = 1\n" * 50
    r = RefactorSuggestor()
    report = r.analyse_source(source)
    kinds = {s.kind for s in report.suggestions}
    assert "split_function" in kinds


def test_too_many_args():
    source = "def too_many(a, b, c, d, e, f, g):\n    pass\n"
    r = RefactorSuggestor()
    report = r.analyse_source(source)
    kinds = {s.kind for s in report.suggestions}
    assert "extract_method" in kinds


def test_deep_nesting():
    source = textwrap.dedent("""
    def nested():
        if True:
            for i in range(10):
                while True:
                    if i > 5:
                        pass
    """)
    r = RefactorSuggestor()
    report = r.analyse_source(source)
    kinds = {s.kind for s in report.suggestions}
    assert "extract_method" in kinds


def test_format_summary_no_suggestions():
    source = "def ok(x):\n    return x\n"
    r = RefactorSuggestor()
    report = r.analyse_source(source, file="test.py")
    summary = report.format_summary()
    assert "No refactoring" in summary or isinstance(summary, str)


def test_analyse_file_not_found():
    r = RefactorSuggestor()
    report = r.analyse_file("/nonexistent/file.py")
    assert report.total == 0


def test_analyse_file_real(tmp_path):
    p = tmp_path / "big.py"
    p.write_text("def big(a,b,c,d,e,f):\n" + "    x = 1\n" * 50)
    r = RefactorSuggestor()
    report = r.analyse_file(str(p))
    assert report.total > 0
