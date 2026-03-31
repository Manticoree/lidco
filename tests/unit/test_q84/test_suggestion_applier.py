"""Tests for SuggestionApplier (T553)."""
from __future__ import annotations
from pathlib import Path
import pytest
from lidco.review.suggestion_applier import SuggestionApplier, Suggestion, SuggestionApplyResult, ApplyBatch


def test_parse_suggestions_basic():
    review = """\
In `src/mod.py` line 5, replace the function:
```old
def foo():
    pass
```
```suggestion
def foo():
    return 42
```
"""
    applier = SuggestionApplier(".")
    sug = applier.parse_suggestions(review)
    assert len(sug) >= 1
    assert "42" in sug[0].new_code


def test_apply_replaces_content(tmp_path):
    p = tmp_path / "mod.py"
    p.write_text("def foo():\n    pass\n")
    applier = SuggestionApplier(tmp_path)
    s = Suggestion(file="mod.py", description="fix foo", old_code="    pass", new_code="    return 42")
    result = applier.apply(s)
    assert result.success
    assert "42" in p.read_text()


def test_apply_file_not_found(tmp_path):
    applier = SuggestionApplier(tmp_path)
    s = Suggestion(file="missing.py", description="x", old_code="x", new_code="y")
    result = applier.apply(s)
    assert not result.success
    assert "not found" in result.message.lower()


def test_apply_old_code_not_found(tmp_path):
    p = tmp_path / "mod.py"
    p.write_text("x = 1\n")
    applier = SuggestionApplier(tmp_path)
    s = Suggestion(file="mod.py", description="x", old_code="DOES_NOT_EXIST", new_code="y")
    result = applier.apply(s)
    assert not result.success


def test_apply_no_file_specified(tmp_path):
    applier = SuggestionApplier(tmp_path)
    s = Suggestion(file="", description="x", old_code="x", new_code="y")
    result = applier.apply(s)
    assert not result.success


def test_apply_all_batch(tmp_path):
    (tmp_path / "a.py").write_text("OLD_A\n")
    (tmp_path / "b.py").write_text("OLD_B\n")
    applier = SuggestionApplier(tmp_path)
    suggestions = [
        Suggestion(file="a.py", description="fix a", old_code="OLD_A", new_code="NEW_A"),
        Suggestion(file="b.py", description="fix b", old_code="OLD_B", new_code="NEW_B"),
    ]
    batch = applier.apply_all(suggestions)
    assert batch.applied == 2
    assert batch.failed == 0


def test_apply_dry_run_no_write(tmp_path):
    p = tmp_path / "mod.py"
    p.write_text("OLD\n")
    applier = SuggestionApplier(tmp_path)
    s = Suggestion(file="mod.py", description="x", old_code="OLD", new_code="NEW")
    result = applier.apply(s, dry_run=True)
    assert result.success
    assert p.read_text() == "OLD\n"  # unchanged


def test_batch_success_rate():
    batch = ApplyBatch(results=[], applied=3, failed=1, skipped=0)
    assert batch.success_rate == pytest.approx(0.75)
