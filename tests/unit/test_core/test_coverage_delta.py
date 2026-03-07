"""Tests for coverage_delta — before/after coverage comparison."""

from __future__ import annotations

import pytest

from lidco.core.coverage_delta import CoverageDelta, compute_delta, format_delta
from lidco.core.coverage_gap import FileCoverageInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_info(
    path: str,
    executed: list[int],
    missing: list[int],
    pct: float,
) -> FileCoverageInfo:
    return FileCoverageInfo(
        file_path=path,
        executed_lines=executed,
        missing_lines=missing,
        excluded_lines=[],
        missing_branches=[],
        coverage_pct=pct,
    )


# ---------------------------------------------------------------------------
# CoverageDelta dataclass
# ---------------------------------------------------------------------------


class TestCoverageDelta:
    def test_frozen(self):
        d = CoverageDelta("f.py", 80.0, 90.0, 10.0, [], [])
        with pytest.raises((AttributeError, TypeError)):
            d.delta_pct = 0.0  # type: ignore[misc]

    def test_fields(self):
        d = CoverageDelta("f.py", 70.0, 85.0, 15.0, [5, 6], [])
        assert d.file_path == "f.py"
        assert d.before_pct == pytest.approx(70.0)
        assert d.after_pct == pytest.approx(85.0)
        assert d.delta_pct == pytest.approx(15.0)
        assert d.newly_covered == [5, 6]
        assert d.newly_missing == []


# ---------------------------------------------------------------------------
# compute_delta
# ---------------------------------------------------------------------------


class TestComputeDelta:
    def test_improvement_detected(self):
        before = {"f.py": _make_info("f.py", [1, 2], [3, 4], 50.0)}
        after = {"f.py": _make_info("f.py", [1, 2, 3, 4], [], 100.0)}
        deltas = compute_delta(before, after)
        assert len(deltas) == 1
        d = deltas[0]
        assert d.delta_pct == pytest.approx(50.0)
        assert 3 in d.newly_covered
        assert 4 in d.newly_covered

    def test_regression_detected(self):
        before = {"f.py": _make_info("f.py", [1, 2, 3], [], 100.0)}
        after = {"f.py": _make_info("f.py", [1, 2], [3], 66.7)}
        deltas = compute_delta(before, after)
        assert len(deltas) == 1
        d = deltas[0]
        assert d.delta_pct < 0
        assert 3 in d.newly_missing

    def test_no_change_excluded(self):
        info = _make_info("f.py", [1, 2], [3], 66.7)
        deltas = compute_delta({"f.py": info}, {"f.py": info})
        assert deltas == []

    def test_new_file_in_after(self):
        after = {"new.py": _make_info("new.py", [1, 2], [], 100.0)}
        deltas = compute_delta({}, after)
        assert any(d.file_path == "new.py" for d in deltas)
        d = next(d for d in deltas if d.file_path == "new.py")
        assert d.before_pct == pytest.approx(0.0)

    def test_removed_file_in_before(self):
        before = {"old.py": _make_info("old.py", [1, 2, 3], [], 100.0)}
        deltas = compute_delta(before, {})
        assert any(d.file_path == "old.py" for d in deltas)
        d = next(d for d in deltas if d.file_path == "old.py")
        assert d.after_pct == pytest.approx(0.0)

    def test_sorted_by_abs_delta_descending(self):
        before = {
            "a.py": _make_info("a.py", [1], [2], 50.0),
            "b.py": _make_info("b.py", [1, 2], [3], 66.0),
        }
        after = {
            "a.py": _make_info("a.py", [1, 2], [], 100.0),  # +50
            "b.py": _make_info("b.py", [1, 2, 3], [], 100.0),  # +34
        }
        deltas = compute_delta(before, after)
        assert deltas[0].file_path == "a.py"

    def test_empty_both_returns_empty(self):
        assert compute_delta({}, {}) == []

    def test_multiple_files(self):
        before = {
            "a.py": _make_info("a.py", [1], [2, 3], 33.0),
            "b.py": _make_info("b.py", [1, 2, 3], [], 100.0),
        }
        after = {
            "a.py": _make_info("a.py", [1, 2, 3], [], 100.0),
            "b.py": _make_info("b.py", [1, 2, 3], [], 100.0),
        }
        deltas = compute_delta(before, after)
        # b.py unchanged → excluded; only a.py has delta
        assert len(deltas) == 1
        assert deltas[0].file_path == "a.py"

    def test_newly_covered_sorted(self):
        before = {"f.py": _make_info("f.py", [1], [5, 3, 7], 25.0)}
        after = {"f.py": _make_info("f.py", [1, 3, 5, 7], [], 100.0)}
        deltas = compute_delta(before, after)
        assert deltas[0].newly_covered == sorted(deltas[0].newly_covered)


# ---------------------------------------------------------------------------
# format_delta
# ---------------------------------------------------------------------------


class TestFormatDelta:
    def test_empty_returns_ok(self):
        result = format_delta([])
        assert "[OK]" in result or "no" in result.lower()

    def test_improvement_icon(self):
        d = CoverageDelta("f.py", 50.0, 100.0, 50.0, [3, 4], [])
        result = format_delta([d])
        assert "✅" in result
        assert "f.py" in result

    def test_regression_icon(self):
        d = CoverageDelta("f.py", 100.0, 50.0, -50.0, [], [3])
        result = format_delta([d])
        assert "⚠" in result

    def test_newly_covered_shown(self):
        d = CoverageDelta("f.py", 50.0, 100.0, 50.0, [3, 4, 5], [])
        result = format_delta([d])
        assert "3" in result

    def test_newly_missing_shown(self):
        d = CoverageDelta("f.py", 100.0, 66.0, -34.0, [], [7, 8])
        result = format_delta([d])
        assert "7" in result

    def test_markdown_header(self):
        d = CoverageDelta("f.py", 50.0, 60.0, 10.0, [1], [])
        result = format_delta([d])
        assert "#" in result

    def test_before_after_percentages_shown(self):
        d = CoverageDelta("f.py", 60.0, 80.0, 20.0, [], [])
        result = format_delta([d])
        assert "60" in result
        assert "80" in result
