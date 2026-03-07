"""Tests for flake_classifier — root-cause category detection for flaky tests."""

from __future__ import annotations

import pytest

from lidco.core.flake_classifier import (
    FlakeCategory,
    FlakeClassification,
    classify_flake,
    classify_many,
)
from lidco.core.flake_detector import FlakeRecord, TestOutcome


# ---------------------------------------------------------------------------
# FlakeCategory enum
# ---------------------------------------------------------------------------


class TestFlakeCategoryEnum:
    def test_categories_exist(self):
        assert hasattr(FlakeCategory, "TIMING")
        assert hasattr(FlakeCategory, "ORDERING")
        assert hasattr(FlakeCategory, "RESOURCE")
        assert hasattr(FlakeCategory, "RANDOM")
        assert hasattr(FlakeCategory, "UNKNOWN")

    def test_string_values(self):
        assert FlakeCategory.TIMING.value == "timing"
        assert FlakeCategory.ORDERING.value == "ordering"
        assert FlakeCategory.RESOURCE.value == "resource"
        assert FlakeCategory.RANDOM.value == "random"
        assert FlakeCategory.UNKNOWN.value == "unknown"


# ---------------------------------------------------------------------------
# FlakeClassification dataclass
# ---------------------------------------------------------------------------


class TestFlakeClassification:
    def test_frozen(self):
        c = FlakeClassification(
            test_id="t",
            category=FlakeCategory.TIMING,
            confidence=0.8,
            reason="timeout",
        )
        with pytest.raises((AttributeError, TypeError)):
            c.category = FlakeCategory.RANDOM  # type: ignore[misc]

    def test_fields(self):
        c = FlakeClassification(
            test_id="foo",
            category=FlakeCategory.RESOURCE,
            confidence=0.9,
            reason="port in use",
        )
        assert c.test_id == "foo"
        assert c.category == FlakeCategory.RESOURCE
        assert c.confidence == pytest.approx(0.9)
        assert c.reason == "port in use"


# ---------------------------------------------------------------------------
# classify_flake — TIMING
# ---------------------------------------------------------------------------


class TestClassifyTiming:
    def _outcomes(self, error_msgs: list[str | None]) -> list[TestOutcome]:
        return [
            TestOutcome("t", passed=(m is None), duration_s=0.1, error_msg=m)
            for m in error_msgs
        ]

    def test_timeout_message_detected(self):
        outcomes = self._outcomes(["TimeoutError: test timed out after 5s", None, None])
        rec = FlakeRecord("t", runs=3, failures=1, flake_rate=1/3)
        clf = classify_flake(rec, outcomes)
        assert clf.category == FlakeCategory.TIMING

    def test_slow_assertion_detected(self):
        outcomes = self._outcomes(["AssertionError: expected response within 2s"])
        rec = FlakeRecord("t", runs=1, failures=1, flake_rate=1.0)
        clf = classify_flake(rec, outcomes)
        assert clf.category == FlakeCategory.TIMING

    def test_deadline_exceeded(self):
        outcomes = self._outcomes(["DeadlineExceeded: operation deadline exceeded"])
        rec = FlakeRecord("t", runs=1, failures=1, flake_rate=1.0)
        clf = classify_flake(rec, outcomes)
        assert clf.category == FlakeCategory.TIMING


# ---------------------------------------------------------------------------
# classify_flake — ORDERING
# ---------------------------------------------------------------------------


class TestClassifyOrdering:
    def _rec_outcomes(self, error_msg: str) -> tuple[FlakeRecord, list[TestOutcome]]:
        outcomes = [TestOutcome("t", False, 0.1, error_msg)]
        return FlakeRecord("t", 1, 1, 1.0), outcomes

    def test_fixture_error(self):
        rec, outcomes = self._rec_outcomes("fixture 'db' not found")
        clf = classify_flake(rec, outcomes)
        assert clf.category == FlakeCategory.ORDERING

    def test_setup_failed(self):
        rec, outcomes = self._rec_outcomes("ERROR at setup of test_bar")
        clf = classify_flake(rec, outcomes)
        assert clf.category == FlakeCategory.ORDERING

    def test_teardown_failed(self):
        rec, outcomes = self._rec_outcomes("ERROR at teardown of test_bar")
        clf = classify_flake(rec, outcomes)
        assert clf.category == FlakeCategory.ORDERING

    def test_test_depends_on_order(self):
        rec, outcomes = self._rec_outcomes("AttributeError: 'NoneType' object has no attribute 'cursor'")
        clf = classify_flake(rec, outcomes)
        # May classify as ORDERING or UNKNOWN — just must not crash
        assert clf.category in (FlakeCategory.ORDERING, FlakeCategory.UNKNOWN)


# ---------------------------------------------------------------------------
# classify_flake — RESOURCE
# ---------------------------------------------------------------------------


class TestClassifyResource:
    def _rec_outcomes(self, error_msg: str) -> tuple[FlakeRecord, list[TestOutcome]]:
        outcomes = [TestOutcome("t", False, 0.1, error_msg)]
        return FlakeRecord("t", 1, 1, 1.0), outcomes

    def test_address_in_use(self):
        rec, outcomes = self._rec_outcomes("OSError: [Errno 98] Address already in use")
        clf = classify_flake(rec, outcomes)
        assert clf.category == FlakeCategory.RESOURCE

    def test_file_not_found(self):
        rec, outcomes = self._rec_outcomes("FileNotFoundError: /tmp/test_output.txt")
        clf = classify_flake(rec, outcomes)
        assert clf.category == FlakeCategory.RESOURCE

    def test_permission_denied(self):
        rec, outcomes = self._rec_outcomes("PermissionError: [Errno 13] Permission denied")
        clf = classify_flake(rec, outcomes)
        assert clf.category == FlakeCategory.RESOURCE

    def test_no_space_left(self):
        rec, outcomes = self._rec_outcomes("OSError: [Errno 28] No space left on device")
        clf = classify_flake(rec, outcomes)
        assert clf.category == FlakeCategory.RESOURCE


# ---------------------------------------------------------------------------
# classify_flake — RANDOM
# ---------------------------------------------------------------------------


class TestClassifyRandom:
    def _rec_outcomes(self, error_msg: str) -> tuple[FlakeRecord, list[TestOutcome]]:
        outcomes = [TestOutcome("t", False, 0.1, error_msg)]
        return FlakeRecord("t", 1, 1, 1.0), outcomes

    def test_random_seed(self):
        rec, outcomes = self._rec_outcomes("AssertionError: random seed 42 produced wrong output")
        clf = classify_flake(rec, outcomes)
        assert clf.category == FlakeCategory.RANDOM

    def test_nondeterministic_hash(self):
        rec, outcomes = self._rec_outcomes("AssertionError: dict ordering inconsistent (PYTHONHASHSEED)")
        clf = classify_flake(rec, outcomes)
        assert clf.category == FlakeCategory.RANDOM

    def test_uuid_mismatch(self):
        rec, outcomes = self._rec_outcomes("AssertionError: uuid4() value changed between runs")
        clf = classify_flake(rec, outcomes)
        assert clf.category == FlakeCategory.RANDOM


# ---------------------------------------------------------------------------
# classify_flake — UNKNOWN fallback
# ---------------------------------------------------------------------------


class TestClassifyUnknown:
    def test_no_error_msgs_unknown(self):
        outcomes = [TestOutcome("t", True, 0.1, None)]
        rec = FlakeRecord("t", 1, 0, 0.0)
        clf = classify_flake(rec, outcomes)
        assert clf.category == FlakeCategory.UNKNOWN

    def test_unrecognised_error_unknown(self):
        outcomes = [TestOutcome("t", False, 0.1, "Something completely unrecognised xyz123")]
        rec = FlakeRecord("t", 1, 1, 1.0)
        clf = classify_flake(rec, outcomes)
        assert clf.category == FlakeCategory.UNKNOWN

    def test_none_error_msgs_unknown(self):
        outcomes: list[TestOutcome] = []
        rec = FlakeRecord("t", 3, 1, 1/3)
        clf = classify_flake(rec, outcomes)
        assert clf.category == FlakeCategory.UNKNOWN


# ---------------------------------------------------------------------------
# classify_many
# ---------------------------------------------------------------------------


class TestClassifyMany:
    def test_empty_returns_empty(self):
        result = classify_many([], {})
        assert result == []

    def test_classifies_multiple(self):
        records = [
            FlakeRecord("a", 3, 1, 1/3),
            FlakeRecord("b", 3, 2, 2/3),
        ]
        outcomes_map = {
            "a": [TestOutcome("a", False, 0.1, "TimeoutError")],
            "b": [TestOutcome("b", False, 0.1, "FileNotFoundError: missing")],
        }
        results = classify_many(records, outcomes_map)
        assert len(results) == 2
        cats = {r.test_id: r.category for r in results}
        assert cats["a"] == FlakeCategory.TIMING
        assert cats["b"] == FlakeCategory.RESOURCE

    def test_missing_outcomes_uses_unknown(self):
        records = [FlakeRecord("x", 2, 1, 0.5)]
        results = classify_many(records, {})
        assert results[0].category == FlakeCategory.UNKNOWN
