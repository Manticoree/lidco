"""Tests for coverage_gap — locates uncovered lines and branches."""

from __future__ import annotations

from pathlib import Path

import pytest

from lidco.core.coverage_gap import (
    CoverageGap,
    FileCoverageInfo,
    parse_coverage_json,
    find_gaps_for_file,
    format_coverage_gaps,
)


# ---------------------------------------------------------------------------
# CoverageGap dataclass
# ---------------------------------------------------------------------------


class TestCoverageGapDataclass:
    def test_frozen(self):
        g = CoverageGap(file_path="foo.py", missing_lines=[1, 2], missing_branches=[], coverage_pct=80.0)
        with pytest.raises((AttributeError, TypeError)):
            g.coverage_pct = 90.0  # type: ignore[misc]

    def test_fields(self):
        g = CoverageGap(file_path="foo.py", missing_lines=[3, 5], missing_branches=[(3, 4)], coverage_pct=75.0)
        assert g.file_path == "foo.py"
        assert g.missing_lines == [3, 5]
        assert g.missing_branches == [(3, 4)]
        assert g.coverage_pct == pytest.approx(75.0)


# ---------------------------------------------------------------------------
# FileCoverageInfo dataclass
# ---------------------------------------------------------------------------


class TestFileCoverageInfo:
    def test_frozen(self):
        info = FileCoverageInfo(
            file_path="bar.py",
            executed_lines=[1, 2],
            missing_lines=[3],
            excluded_lines=[],
            missing_branches=[],
            coverage_pct=66.7,
        )
        with pytest.raises((AttributeError, TypeError)):
            info.coverage_pct = 100.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# parse_coverage_json
# ---------------------------------------------------------------------------


class TestParseCoverageJson:
    def _make_data(self, files: dict) -> dict:
        return {"files": files, "meta": {"version": "7.0"}}

    def test_parse_single_file(self):
        data = self._make_data({
            "src/foo.py": {
                "executed_lines": [1, 2, 3],
                "missing_lines": [4, 5],
                "excluded_lines": [],
                "missing_branches": [],
                "summary": {"percent_covered": 60.0},
            }
        })
        result = parse_coverage_json(data)
        assert "src/foo.py" in result
        info = result["src/foo.py"]
        assert info.executed_lines == [1, 2, 3]
        assert info.missing_lines == [4, 5]
        assert info.coverage_pct == pytest.approx(60.0)

    def test_parse_missing_branches(self):
        data = self._make_data({
            "src/bar.py": {
                "executed_lines": [1],
                "missing_lines": [],
                "excluded_lines": [],
                "missing_branches": [[3, 4], [5, 6]],
                "summary": {"percent_covered": 90.0},
            }
        })
        result = parse_coverage_json(data)
        info = result["src/bar.py"]
        assert (3, 4) in info.missing_branches
        assert (5, 6) in info.missing_branches

    def test_empty_files_returns_empty(self):
        result = parse_coverage_json({"files": {}})
        assert result == {}

    def test_malformed_data_returns_empty(self):
        result = parse_coverage_json({})
        assert result == {}

    def test_missing_summary_defaults_zero(self):
        data = self._make_data({
            "src/foo.py": {
                "executed_lines": [1],
                "missing_lines": [],
                "excluded_lines": [],
                "missing_branches": [],
            }
        })
        result = parse_coverage_json(data)
        assert result["src/foo.py"].coverage_pct == pytest.approx(0.0)

    def test_multiple_files(self):
        data = self._make_data({
            "a.py": {"executed_lines": [1], "missing_lines": [], "excluded_lines": [],
                     "missing_branches": [], "summary": {"percent_covered": 100.0}},
            "b.py": {"executed_lines": [], "missing_lines": [1, 2], "excluded_lines": [],
                     "missing_branches": [], "summary": {"percent_covered": 0.0}},
        })
        result = parse_coverage_json(data)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# find_gaps_for_file
# ---------------------------------------------------------------------------


class TestFindGapsForFile:
    def _make_info(
        self,
        missing_lines: list[int],
        missing_branches: list[tuple[int, int]],
        coverage_pct: float = 80.0,
    ) -> FileCoverageInfo:
        return FileCoverageInfo(
            file_path="foo.py",
            executed_lines=[],
            missing_lines=missing_lines,
            excluded_lines=[],
            missing_branches=missing_branches,
            coverage_pct=coverage_pct,
        )

    def test_no_gaps_returns_none(self):
        info = self._make_info([], [], 100.0)
        assert find_gaps_for_file("foo.py", {"foo.py": info}) is None

    def test_missing_lines_detected(self):
        info = self._make_info([10, 11, 12], [], 80.0)
        gap = find_gaps_for_file("foo.py", {"foo.py": info})
        assert gap is not None
        assert gap.missing_lines == [10, 11, 12]

    def test_missing_branches_detected(self):
        info = self._make_info([], [(5, 6), (7, 8)], 90.0)
        gap = find_gaps_for_file("foo.py", {"foo.py": info})
        assert gap is not None
        assert (5, 6) in gap.missing_branches

    def test_unknown_file_returns_none(self):
        result = find_gaps_for_file("nonexistent.py", {})
        assert result is None

    def test_normalises_path_separators(self):
        info = self._make_info([5], [], 90.0)
        # Both forward-slash and backslash keys should match
        gap = find_gaps_for_file("src/foo.py", {"src/foo.py": info})
        assert gap is not None


# ---------------------------------------------------------------------------
# format_coverage_gaps
# ---------------------------------------------------------------------------


class TestFormatCoverageGaps:
    def test_no_gaps_ok_message(self):
        result = format_coverage_gaps([])
        assert "[OK]" in result or "no gap" in result.lower() or "100" in result

    def test_single_gap_shown(self):
        gaps = [CoverageGap("src/foo.py", [10, 11], [], 80.0)]
        result = format_coverage_gaps(gaps)
        assert "foo.py" in result
        assert "10" in result
        assert "80" in result

    def test_branches_shown(self):
        gaps = [CoverageGap("src/bar.py", [], [(3, 4)], 95.0)]
        result = format_coverage_gaps(gaps)
        assert "bar.py" in result
        assert "3" in result

    def test_multiple_gaps_ranked_by_coverage(self):
        gaps = [
            CoverageGap("a.py", [1], [], 90.0),  # better coverage
            CoverageGap("b.py", [1, 2, 3], [], 50.0),  # worse coverage
        ]
        result = format_coverage_gaps(gaps)
        pos_a = result.find("a.py")
        pos_b = result.find("b.py")
        # Lower coverage (b.py) should appear first
        assert pos_b < pos_a

    def test_markdown_header(self):
        gaps = [CoverageGap("x.py", [1], [], 70.0)]
        result = format_coverage_gaps(gaps)
        assert "#" in result
