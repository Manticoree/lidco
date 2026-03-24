"""Tests for ErrorExplainer (T565)."""
from __future__ import annotations
import pytest
from lidco.analysis.error_explainer import ErrorExplainer, _parse_traceback


TRACEBACK = """
Traceback (most recent call last):
  File "src/app.py", line 42, in handler
    result = data["key"]
KeyError: 'key'
"""


def test_parse_error_type():
    err = _parse_traceback(TRACEBACK)
    assert err.error_type == "KeyError"


def test_parse_file_and_line():
    err = _parse_traceback(TRACEBACK)
    assert "app.py" in err.file
    assert err.line == 42


def test_parse_frames():
    err = _parse_traceback(TRACEBACK)
    assert len(err.traceback_frames) >= 1


def test_explain_keyerror():
    e = ErrorExplainer()
    exp = e.explain(TRACEBACK)
    assert exp.error.error_type == "KeyError"
    assert len(exp.suggestions) >= 1
    assert exp.suggestions[0].confidence > 0.5


def test_explain_importerror():
    tb = "Traceback:\n  File x.py, line 1\nModuleNotFoundError: No module named 'requests'"
    e = ErrorExplainer()
    exp = e.explain(tb)
    assert any("pip install" in s.fix for s in exp.suggestions)


def test_explain_text_format():
    e = ErrorExplainer()
    out = e.explain_text(TRACEBACK)
    assert "KeyError" in out


def test_explain_attributeerror():
    tb = "Traceback:\n  File a.py, line 5\nAttributeError: 'NoneType' object has no attribute 'strip'"
    e = ErrorExplainer()
    exp = e.explain(tb)
    assert len(exp.suggestions) >= 1


def test_format_includes_file():
    e = ErrorExplainer()
    exp = e.explain(TRACEBACK)
    fmt = exp.format()
    assert "app.py" in fmt
