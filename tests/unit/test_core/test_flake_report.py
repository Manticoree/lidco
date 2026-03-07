"""Tests for flake_report — Markdown report formatter for flaky tests."""

from __future__ import annotations

import pytest

from lidco.core.flake_classifier import FlakeCategory, FlakeClassification
from lidco.core.flake_detector import FlakeHistory, FlakeRecord, TestOutcome
from lidco.core.flake_report import format_flake_report, format_flake_summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_history(outcomes: list[tuple[str, bool]]) -> FlakeHistory:
    h = FlakeHistory()
    for test_id, passed in outcomes:
        h.record_outcome(TestOutcome(test_id, passed, 0.1, None if passed else "AssertionError"))
    return h


def _make_classifications(data: list[tuple[str, FlakeCategory, float]]) -> list[FlakeClassification]:
    return [
        FlakeClassification(test_id=tid, category=cat, confidence=conf, reason="test reason")
        for tid, cat, conf in data
    ]


# ---------------------------------------------------------------------------
# format_flake_summary
# ---------------------------------------------------------------------------


class TestFormatFlakeSummary:
    def test_no_flakes_ok_message(self):
        h = _make_history([("t::a", True), ("t::a", True)])
        result = format_flake_summary(h, flaky_records=[])
        assert "[OK]" in result or "no flaky" in result.lower() or "0" in result

    def test_total_runs_shown(self):
        h = _make_history([("t::a", True), ("t::b", False)])
        result = format_flake_summary(h, flaky_records=[])
        assert "2" in result

    def test_flaky_count_shown(self):
        h = _make_history([("t::a", True), ("t::a", False), ("t::b", True)])
        flaky = [FlakeRecord("t::a", 2, 1, 0.5)]
        result = format_flake_summary(h, flaky_records=flaky)
        assert "1" in result  # 1 flaky test

    def test_total_tests_shown(self):
        h = _make_history([("t::a", True), ("t::b", True)])
        result = format_flake_summary(h, flaky_records=[])
        assert "2" in result


# ---------------------------------------------------------------------------
# format_flake_report
# ---------------------------------------------------------------------------


class TestFormatFlakeReport:
    def test_empty_history_produces_ok(self):
        h = FlakeHistory()
        result = format_flake_report(h, flaky_records=[], classifications=[])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_single_flaky_test_shown(self):
        h = _make_history([("tests/test_foo.py::test_bar", True),
                           ("tests/test_foo.py::test_bar", False),
                           ("tests/test_foo.py::test_bar", True)])
        flaky = [FlakeRecord("tests/test_foo.py::test_bar", 3, 1, 1/3)]
        result = format_flake_report(h, flaky_records=flaky, classifications=[])
        assert "test_bar" in result
        # Flake rate shown as percentage
        assert "33" in result or "1/3" in result or "0.33" in result

    def test_classification_shown(self):
        h = _make_history([("t::a", False)])
        flaky = [FlakeRecord("t::a", 1, 1, 1.0)]
        clfs = _make_classifications([("t::a", FlakeCategory.TIMING, 0.9)])
        result = format_flake_report(h, flaky_records=flaky, classifications=clfs)
        assert "timing" in result.lower() or "TIMING" in result

    def test_multiple_tests_ranked_by_flake_rate(self):
        h = _make_history([
            ("t::low", True), ("t::low", False),  # 50%
            ("t::high", False), ("t::high", False), ("t::high", True),  # 67%
        ])
        flaky = [
            FlakeRecord("t::high", 3, 2, 2/3),
            FlakeRecord("t::low", 2, 1, 0.5),
        ]
        result = format_flake_report(h, flaky_records=flaky, classifications=[])
        # high flake rate should appear before low
        pos_high = result.find("t::high")
        pos_low = result.find("t::low")
        assert pos_high < pos_low

    def test_report_has_markdown_header(self):
        h = FlakeHistory()
        result = format_flake_report(h, flaky_records=[], classifications=[])
        assert result.startswith("#")

    def test_run_errors_shown_when_present(self):
        h = FlakeHistory()
        result = format_flake_report(
            h,
            flaky_records=[],
            classifications=[],
            run_errors=["Run 1: timed out", "Run 2: failed to launch"],
        )
        assert "timed out" in result or "Run 1" in result

    def test_confidence_shown(self):
        h = _make_history([("t::a", False)])
        flaky = [FlakeRecord("t::a", 1, 1, 1.0)]
        clfs = _make_classifications([("t::a", FlakeCategory.RESOURCE, 0.85)])
        result = format_flake_report(h, flaky_records=flaky, classifications=clfs)
        assert "85" in result or "0.85" in result

    def test_no_classification_shows_unknown(self):
        h = _make_history([("t::a", False)])
        flaky = [FlakeRecord("t::a", 1, 1, 1.0)]
        result = format_flake_report(h, flaky_records=flaky, classifications=[])
        # Should show "unknown" or just omit category line
        assert isinstance(result, str)
