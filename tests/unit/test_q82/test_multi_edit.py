"""Tests for MultiEditTransaction (T533)."""
from __future__ import annotations
from pathlib import Path
import pytest
from lidco.editing.multi_edit import MultiEditTransaction, TransactionResult


def test_add_and_apply(tmp_path):
    p = tmp_path / "f.py"
    p.write_text("x = 1\n")
    tx = MultiEditTransaction()
    tx.add_edit(str(p), "x = 1", "x = 2")
    result = tx.apply()
    assert result.applied == 1
    assert result.failed == 0
    assert p.read_text() == "x = 2\n"


def test_validate_file_not_found(tmp_path):
    tx = MultiEditTransaction()
    tx.add_edit(str(tmp_path / "missing.py"), "a", "b")
    errors = tx.validate()
    assert len(errors) == 1
    assert "not found" in errors[0]


def test_validate_old_string_not_found(tmp_path):
    p = tmp_path / "f.py"
    p.write_text("hello\n")
    tx = MultiEditTransaction()
    tx.add_edit(str(p), "world", "earth")
    errors = tx.validate()
    assert len(errors) == 1


def test_validate_ambiguous_without_replace_all(tmp_path):
    p = tmp_path / "f.py"
    p.write_text("x\nx\n")
    tx = MultiEditTransaction()
    tx.add_edit(str(p), "x", "y")
    errors = tx.validate()
    assert len(errors) == 1
    assert "replace_all" in errors[0]


def test_rollback(tmp_path):
    p = tmp_path / "f.py"
    p.write_text("a = 1\n")
    tx = MultiEditTransaction()
    tx.add_edit(str(p), "a = 1", "b = 2")
    tx.apply()
    assert p.read_text() == "b = 2\n"
    tx.rollback()
    assert p.read_text() == "a = 1\n"


def test_result_success_property():
    r = TransactionResult(applied=2, failed=0)
    assert r.success is True
    r2 = TransactionResult(applied=1, failed=1, errors=["err"])
    assert r2.success is False


def test_step_count():
    tx = MultiEditTransaction()
    tx.add_edit("a.py", "x", "y")
    tx.add_edit("b.py", "p", "q")
    assert tx.step_count == 2


def test_apply_multiple_steps(tmp_path):
    p1 = tmp_path / "a.py"
    p2 = tmp_path / "b.py"
    p1.write_text("foo = 1\n")
    p2.write_text("bar = 2\n")
    tx = MultiEditTransaction()
    tx.add_edit(str(p1), "foo = 1", "foo = 10")
    tx.add_edit(str(p2), "bar = 2", "bar = 20")
    result = tx.apply()
    assert result.applied == 2
    assert result.failed == 0
