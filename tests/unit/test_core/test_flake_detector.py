"""Tests for flake_detector — core data model for flaky test detection."""

from __future__ import annotations

import pytest

from lidco.core.flake_detector import (
    FlakeHistory,
    FlakeRecord,
    TestOutcome,
)


# ---------------------------------------------------------------------------
# TestOutcome
# ---------------------------------------------------------------------------


class TestTestOutcome:
    def test_frozen(self):
        o = TestOutcome(test_id="test_foo", passed=True, duration_s=0.1, error_msg=None)
        with pytest.raises((AttributeError, TypeError)):
            o.passed = False  # type: ignore[misc]

    def test_fields(self):
        o = TestOutcome(test_id="test_bar", passed=False, duration_s=1.5, error_msg="AssertionError")
        assert o.test_id == "test_bar"
        assert o.passed is False
        assert o.duration_s == 1.5
        assert o.error_msg == "AssertionError"

    def test_none_error_msg_for_pass(self):
        o = TestOutcome(test_id="t", passed=True, duration_s=0.0, error_msg=None)
        assert o.error_msg is None


# ---------------------------------------------------------------------------
# FlakeRecord
# ---------------------------------------------------------------------------


class TestFlakeRecord:
    def test_frozen(self):
        r = FlakeRecord(test_id="test_x", runs=5, failures=2, flake_rate=0.4)
        with pytest.raises((AttributeError, TypeError)):
            r.failures = 0  # type: ignore[misc]

    def test_flake_rate_calculation(self):
        r = FlakeRecord(test_id="t", runs=10, failures=3, flake_rate=0.3)
        assert r.flake_rate == pytest.approx(0.3)

    def test_zero_failures_zero_rate(self):
        r = FlakeRecord(test_id="t", runs=10, failures=0, flake_rate=0.0)
        assert r.flake_rate == 0.0

    def test_all_failures_rate_one(self):
        r = FlakeRecord(test_id="t", runs=5, failures=5, flake_rate=1.0)
        assert r.flake_rate == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# FlakeHistory — record_outcome
# ---------------------------------------------------------------------------


class TestFlakeHistoryRecord:
    def test_record_pass(self):
        h = FlakeHistory()
        h.record_outcome(TestOutcome("test_a", True, 0.1, None))
        records = h.get_all_records()
        assert len(records) == 1
        assert records[0].test_id == "test_a"
        assert records[0].runs == 1
        assert records[0].failures == 0

    def test_record_fail(self):
        h = FlakeHistory()
        h.record_outcome(TestOutcome("test_a", False, 0.2, "AssertionError"))
        records = h.get_all_records()
        assert records[0].failures == 1
        assert records[0].flake_rate == pytest.approx(1.0)

    def test_multiple_runs_accumulate(self):
        h = FlakeHistory()
        for passed in [True, False, True, False, True]:
            h.record_outcome(TestOutcome("test_a", passed, 0.1, None if passed else "err"))
        rec = h.get_record("test_a")
        assert rec is not None
        assert rec.runs == 5
        assert rec.failures == 2
        assert rec.flake_rate == pytest.approx(0.4)

    def test_multiple_tests_tracked_independently(self):
        h = FlakeHistory()
        h.record_outcome(TestOutcome("test_a", True, 0.1, None))
        h.record_outcome(TestOutcome("test_b", False, 0.2, "err"))
        h.record_outcome(TestOutcome("test_a", False, 0.1, "err"))
        assert h.get_record("test_a").runs == 2
        assert h.get_record("test_b").runs == 1

    def test_flake_rate_updated_on_each_record(self):
        h = FlakeHistory()
        h.record_outcome(TestOutcome("t", False, 0.1, "e"))
        h.record_outcome(TestOutcome("t", False, 0.1, "e"))
        h.record_outcome(TestOutcome("t", True, 0.1, None))
        rec = h.get_record("t")
        assert rec.flake_rate == pytest.approx(2 / 3)


# ---------------------------------------------------------------------------
# FlakeHistory — queries
# ---------------------------------------------------------------------------


class TestFlakeHistoryQueries:
    def test_get_record_returns_none_for_unknown(self):
        h = FlakeHistory()
        assert h.get_record("unknown") is None

    def test_get_all_records_empty(self):
        h = FlakeHistory()
        assert h.get_all_records() == []

    def test_get_flaky_tests_threshold(self):
        h = FlakeHistory()
        # test_a: 1/4 = 25% flake rate
        for passed in [True, False, True, True]:
            h.record_outcome(TestOutcome("test_a", passed, 0.1, None if passed else "e"))
        # test_b: 3/4 = 75% flake rate
        for passed in [False, False, True, False]:
            h.record_outcome(TestOutcome("test_b", passed, 0.1, None if passed else "e"))

        # threshold 0.3 → only test_b qualifies
        flaky = h.get_flaky_tests(min_flake_rate=0.3)
        ids = [r.test_id for r in flaky]
        assert "test_b" in ids
        assert "test_a" not in ids

    def test_get_flaky_tests_sorted_by_rate_desc(self):
        h = FlakeHistory()
        for passed in [True, False]:  # 50%
            h.record_outcome(TestOutcome("medium", passed, 0.1, None if passed else "e"))
        for passed in [False, False, False, True]:  # 75%
            h.record_outcome(TestOutcome("high", passed, 0.1, None if passed else "e"))
        for passed in [False]:  # 100%
            h.record_outcome(TestOutcome("always", passed, 0.1, "e"))

        flaky = h.get_flaky_tests(min_flake_rate=0.0)
        rates = [r.flake_rate for r in flaky]
        assert rates == sorted(rates, reverse=True)

    def test_get_flaky_tests_min_runs_filter(self):
        h = FlakeHistory()
        # Only 1 run — should be excluded when min_runs=2
        h.record_outcome(TestOutcome("one_run", False, 0.1, "e"))
        # 3 runs, 1 failure
        for passed in [True, False, True]:
            h.record_outcome(TestOutcome("three_runs", passed, 0.1, None if passed else "e"))

        flaky = h.get_flaky_tests(min_flake_rate=0.0, min_runs=2)
        ids = [r.test_id for r in flaky]
        assert "one_run" not in ids
        assert "three_runs" in ids

    def test_clear_resets_history(self):
        h = FlakeHistory()
        h.record_outcome(TestOutcome("t", False, 0.1, "e"))
        h.clear()
        assert h.get_all_records() == []
        assert h.get_record("t") is None

    def test_total_runs_property(self):
        h = FlakeHistory()
        h.record_outcome(TestOutcome("a", True, 0.1, None))
        h.record_outcome(TestOutcome("b", True, 0.1, None))
        h.record_outcome(TestOutcome("a", False, 0.1, "e"))
        assert h.total_runs == 3

    def test_total_tests_property(self):
        h = FlakeHistory()
        h.record_outcome(TestOutcome("a", True, 0.1, None))
        h.record_outcome(TestOutcome("b", True, 0.1, None))
        h.record_outcome(TestOutcome("a", False, 0.1, "e"))
        assert h.total_tests == 2
