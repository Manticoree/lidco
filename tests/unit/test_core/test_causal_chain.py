"""Tests for ErrorHistory causal chain analysis."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import pytest

from lidco.core.errors import ErrorRecord, ErrorHistory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(
    error_type: str = "RuntimeError",
    message: str = "something failed",
    file_hint: str | None = None,
    timestamp: datetime | None = None,
) -> ErrorRecord:
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    return ErrorRecord(
        id=uuid.uuid4().hex,
        timestamp=timestamp,
        tool_name="some_tool",
        agent_name="test_agent",
        error_type=error_type,
        message=message,
        traceback_str=None,
        file_hint=file_hint,
    )


BASE_TIME = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_single_error_is_root_cause() -> None:
    history = ErrorHistory()
    rec = _make_record()
    history.append(rec)
    history.infer_causality()
    assert history._records[0].is_root_cause is True
    assert history._records[0].caused_by_id is None


def test_two_unrelated_errors_both_root_causes() -> None:
    history = ErrorHistory()
    t0 = BASE_TIME
    t1 = BASE_TIME + timedelta(seconds=30)
    history.append(_make_record("KeyError", "key not found", "a.py", t0))
    history.append(_make_record("IndexError", "index out of range", "b.py", t1))
    history.infer_causality()
    assert history._records[0].is_root_cause is True
    assert history._records[1].is_root_cause is True


def test_two_linked_errors_same_file_second_is_symptom() -> None:
    history = ErrorHistory()
    t0 = BASE_TIME
    t1 = BASE_TIME + timedelta(seconds=3)
    history.append(_make_record("KeyError", "key not found", "app.py", t0))
    history.append(_make_record("AttributeError", "NoneType has no attribute x", "app.py", t1))
    history.infer_causality()
    assert history._records[1].is_root_cause is False


def test_two_linked_errors_second_has_caused_by_id() -> None:
    history = ErrorHistory()
    t0 = BASE_TIME
    t1 = BASE_TIME + timedelta(seconds=3)
    first = _make_record("KeyError", "key not found", "app.py", t0)
    history.append(first)
    history.append(_make_record("AttributeError", "NoneType has no attribute x", "app.py", t1))
    history.infer_causality()
    assert history._records[1].caused_by_id == history._records[0].id


def test_chain_of_three_only_first_is_root_cause() -> None:
    history = ErrorHistory()
    t0 = BASE_TIME
    t1 = BASE_TIME + timedelta(seconds=2)
    t2 = BASE_TIME + timedelta(seconds=4)
    history.append(_make_record("KeyError", "key not found", "app.py", t0))
    history.append(_make_record("AttributeError", "NoneType has no attribute x", "app.py", t1))
    history.append(_make_record("TypeError", "object is not callable", "app.py", t2))
    history.infer_causality()
    assert history._records[0].is_root_cause is True
    assert history._records[1].is_root_cause is False
    assert history._records[2].is_root_cause is False


def test_time_window_exactly_10s_linked() -> None:
    history = ErrorHistory()
    t0 = BASE_TIME
    t1 = BASE_TIME + timedelta(seconds=10)
    history.append(_make_record("KeyError", "key not found", "app.py", t0))
    history.append(_make_record("AttributeError", "NoneType error", "app.py", t1))
    history.infer_causality()
    assert history._records[1].is_root_cause is False


def test_time_window_11s_not_linked() -> None:
    history = ErrorHistory()
    t0 = BASE_TIME
    t1 = BASE_TIME + timedelta(seconds=11)
    history.append(_make_record("KeyError", "key not found", "app.py", t0))
    history.append(_make_record("AttributeError", "NoneType error", "app.py", t1))
    history.infer_causality()
    assert history._records[1].is_root_cause is True


def test_get_root_causes_returns_only_root_causes() -> None:
    history = ErrorHistory()
    t0 = BASE_TIME
    t1 = BASE_TIME + timedelta(seconds=3)
    history.append(_make_record("KeyError", "key not found", "app.py", t0))
    history.append(_make_record("AttributeError", "NoneType error", "app.py", t1))
    history.infer_causality()
    roots = history.get_root_causes()
    assert len(roots) == 1
    assert roots[0].error_type == "KeyError"


def test_get_root_causes_returns_all_when_no_symptoms() -> None:
    history = ErrorHistory()
    history.append(_make_record("KeyError", "key not found", "a.py", BASE_TIME))
    history.append(_make_record("IndexError", "index error", "b.py", BASE_TIME + timedelta(seconds=30)))
    history.infer_causality()
    roots = history.get_root_causes()
    assert len(roots) == 2


def test_to_causal_chain_str_empty_history() -> None:
    history = ErrorHistory()
    assert history.to_causal_chain_str() == ""


def test_to_causal_chain_str_has_header() -> None:
    history = ErrorHistory()
    history.append(_make_record("KeyError", "key not found", "app.py", BASE_TIME))
    result = history.to_causal_chain_str()
    assert "## Causal Error Chain" in result


def test_to_causal_chain_str_shows_root_line() -> None:
    history = ErrorHistory()
    history.append(_make_record("KeyError", "key not found", "app.py", BASE_TIME))
    result = history.to_causal_chain_str()
    assert "ROOT: KeyError" in result


def test_to_causal_chain_str_shows_symptom_for_linked_errors() -> None:
    history = ErrorHistory()
    t0 = BASE_TIME
    t1 = BASE_TIME + timedelta(seconds=3)
    history.append(_make_record("KeyError", "key not found", "app.py", t0))
    history.append(_make_record("AttributeError", "NoneType has no attribute x", "app.py", t1))
    result = history.to_causal_chain_str()
    assert "└─ SYMPTOM: AttributeError" in result


def test_attributeerror_symptom_pattern_matches() -> None:
    history = ErrorHistory()
    t0 = BASE_TIME
    t1 = BASE_TIME + timedelta(seconds=2)
    history.append(_make_record("RuntimeError", "unexpected failure", "app.py", t0))
    history.append(_make_record("AttributeError", "AttributeError occurred", "app.py", t1))
    history.infer_causality()
    assert history._records[1].is_root_cause is False


def test_has_no_attribute_symptom_pattern_matches() -> None:
    history = ErrorHistory()
    t0 = BASE_TIME
    t1 = BASE_TIME + timedelta(seconds=2)
    history.append(_make_record("RuntimeError", "unexpected failure", "app.py", t0))
    history.append(_make_record("AttributeError", "obj has no attribute 'foo'", "app.py", t1))
    history.infer_causality()
    assert history._records[1].is_root_cause is False


def test_infer_causality_is_idempotent() -> None:
    history = ErrorHistory()
    t0 = BASE_TIME
    t1 = BASE_TIME + timedelta(seconds=3)
    history.append(_make_record("KeyError", "key not found", "app.py", t0))
    history.append(_make_record("AttributeError", "NoneType error", "app.py", t1))
    history.infer_causality()
    state_after_first = [
        (r.is_root_cause, r.caused_by_id) for r in history._records
    ]
    history.infer_causality()
    state_after_second = [
        (r.is_root_cause, r.caused_by_id) for r in history._records
    ]
    assert state_after_first == state_after_second
