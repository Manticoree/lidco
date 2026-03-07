"""Tests for ErrorLedger — cross-session SQLite-backed error persistence."""
from __future__ import annotations

import pytest
from pathlib import Path
from lidco.core.error_ledger import ErrorLedger, _error_hash


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ledger(tmp_path: Path) -> ErrorLedger:
    db = tmp_path / ".lidco" / "error_ledger.db"
    inst = ErrorLedger(db)
    yield inst
    inst.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_record_creates_new_entry(ledger: ErrorLedger) -> None:
    ledger.record("ValueError", "app.py", "main", "something went wrong", "sess-1")
    rows = ledger.get_frequent(min_occurrences=1)
    assert len(rows) == 1
    assert rows[0]["total_occurrences"] == 1
    assert rows[0]["sample_message"] == "something went wrong"


def test_record_upserts_increments_total_occurrences(ledger: ErrorLedger) -> None:
    ledger.record("ValueError", "app.py", "main", "first occurrence", "sess-1")
    ledger.record("ValueError", "app.py", "main", "second occurrence", "sess-1")
    rows = ledger.get_frequent(min_occurrences=1)
    assert len(rows) == 1
    assert rows[0]["total_occurrences"] == 2


def test_sessions_count_increments_on_repeated_record(ledger: ErrorLedger) -> None:
    ledger.record("TypeError", "core.py", "run", "type mismatch", "sess-1")
    ledger.record("TypeError", "core.py", "run", "type mismatch", "sess-2")
    rows = ledger.get_recurring(min_sessions=2)
    assert len(rows) == 1
    assert rows[0]["sessions_count"] == 2


def test_mark_fixed_sets_fix_applied_and_description(ledger: ErrorLedger) -> None:
    ledger.record("RuntimeError", "agent.py", "execute", "failed", "sess-1")
    ledger.mark_fixed("RuntimeError", "agent.py", "execute", "patched null check")
    # Fixed errors should not appear in get_recurring / get_frequent
    recurring = ledger.get_recurring(min_sessions=1)
    frequent = ledger.get_frequent(min_occurrences=1)
    assert recurring == []
    assert frequent == []


def test_get_recurring_returns_only_unfixed_above_threshold(ledger: ErrorLedger) -> None:
    # Error that qualifies (2 sessions)
    ledger.record("KeyError", "b.py", None, "missing key", "s1")
    ledger.record("KeyError", "b.py", None, "missing key", "s2")
    # Error with only 1 session — should not appear
    ledger.record("IndexError", "c.py", None, "out of range", "s1")
    rows = ledger.get_recurring(min_sessions=2)
    assert len(rows) == 1
    assert rows[0]["sessions_count"] == 2


def test_get_recurring_returns_empty_when_none_qualify(ledger: ErrorLedger) -> None:
    ledger.record("KeyError", "b.py", None, "missing key", "s1")
    rows = ledger.get_recurring(min_sessions=3)
    assert rows == []


def test_get_frequent_returns_errors_above_min_occurrences(ledger: ErrorLedger) -> None:
    for _ in range(6):
        ledger.record("OverflowError", "math.py", "calc", "overflow", "s1")
    ledger.record("ZeroDivisionError", "math.py", "div", "division by zero", "s1")
    rows = ledger.get_frequent(min_occurrences=5)
    assert len(rows) == 1
    assert rows[0]["total_occurrences"] == 6


def test_get_frequent_returns_empty_when_none_qualify(ledger: ErrorLedger) -> None:
    ledger.record("OverflowError", "math.py", "calc", "overflow", "s1")
    rows = ledger.get_frequent(min_occurrences=5)
    assert rows == []


def test_summarize_returns_empty_when_no_recurring(ledger: ErrorLedger) -> None:
    # Only 1 session recorded — below the min_sessions=2 threshold
    ledger.record("ValueError", "x.py", None, "bad val", "s1")
    result = ledger.summarize()
    assert result == ""


def test_summarize_returns_markdown_when_recurring_errors_exist(ledger: ErrorLedger) -> None:
    ledger.record("ValueError", "x.py", None, "bad val", "s1")
    ledger.record("ValueError", "x.py", None, "bad val", "s2")
    result = ledger.summarize()
    assert result.startswith("## Recurring Issues (cross-session)")
    assert "seen" in result


def test_error_hash_is_deterministic(tmp_path: Path) -> None:
    h1 = _error_hash("ValueError", "app.py", "main")
    h2 = _error_hash("ValueError", "app.py", "main")
    assert h1 == h2
    assert len(h1) == 16


def test_error_hash_differs_for_different_inputs() -> None:
    h1 = _error_hash("ValueError", "app.py", "main")
    h2 = _error_hash("TypeError", "app.py", "main")
    assert h1 != h2


def test_error_ledger_handles_broken_db_gracefully(tmp_path: Path) -> None:
    # Create a regular file, then try to use it as a directory for the DB path.
    # This forces _init_db() to fail because mkdir will raise NotADirectoryError.
    blocker = tmp_path / "blocker"
    blocker.write_text("I am a file, not a directory")
    bad_path = blocker / "error_ledger.db"  # parent is a file — mkdir will fail
    ledger = ErrorLedger(bad_path)
    # _conn should be None; all methods must be no-ops without raising
    ledger.record("E", None, None, "msg", "s1")
    ledger.mark_fixed("E", None, None, "fixed")
    assert ledger.get_recurring() == []
    assert ledger.get_frequent() == []
    assert ledger.summarize() == ""
    ledger.close()  # must not raise
