"""Tests for branch_counter — branch hit parsing and stats computation."""

from __future__ import annotations

import pytest

from lidco.core.branch_counter import (
    BranchHit,
    BranchStats,
    compute_branch_stats,
    format_branch_stats,
    parse_branch_hits,
)


# ---------------------------------------------------------------------------
# BranchHit dataclass
# ---------------------------------------------------------------------------


class TestBranchHit:
    def test_frozen(self):
        b = BranchHit(from_line=1, to_line=5, hits=3)
        with pytest.raises((AttributeError, TypeError)):
            b.hits = 0  # type: ignore[misc]

    def test_fields(self):
        b = BranchHit(from_line=10, to_line=15, hits=2)
        assert b.from_line == 10
        assert b.to_line == 15
        assert b.hits == 2


# ---------------------------------------------------------------------------
# BranchStats dataclass
# ---------------------------------------------------------------------------


class TestBranchStats:
    def test_frozen(self):
        s = BranchStats("foo.py", total_branches=4, hit_branches=2, miss_branches=2, hit_rate=0.5)
        with pytest.raises((AttributeError, TypeError)):
            s.hit_rate = 1.0  # type: ignore[misc]

    def test_fields(self):
        s = BranchStats("bar.py", total_branches=10, hit_branches=7, miss_branches=3, hit_rate=0.7)
        assert s.file_path == "bar.py"
        assert s.total_branches == 10
        assert s.hit_branches == 7
        assert s.miss_branches == 3
        assert s.hit_rate == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# parse_branch_hits — arcs format
# ---------------------------------------------------------------------------


class TestParseBranchHitsArcs:
    def _make_data(self, file_path: str, arcs: dict) -> dict:
        return {"files": {file_path: {"arcs": arcs}}}

    def test_string_key_format(self):
        data = self._make_data("src/foo.py", {"(1, 5)": 3, "(1, 10)": 0})
        hits = parse_branch_hits(data, "src/foo.py")
        assert len(hits) == 2
        by_dest = {h.to_line: h for h in hits}
        assert by_dest[5].hits == 3
        assert by_dest[10].hits == 0

    def test_hit_positive_miss_zero(self):
        data = self._make_data("src/foo.py", {"(3, 7)": 5, "(3, 9)": 0})
        hits = parse_branch_hits(data, "src/foo.py")
        assert any(h.hits == 5 for h in hits)
        assert any(h.hits == 0 for h in hits)

    def test_unknown_file_returns_empty(self):
        data = self._make_data("src/foo.py", {"(1, 2)": 1})
        result = parse_branch_hits(data, "src/other.py")
        assert result == []

    def test_normalises_path_separators(self):
        data = self._make_data("src/foo.py", {"(1, 5)": 2})
        # backslash variant should match
        result = parse_branch_hits(data, "src\\foo.py")
        assert len(result) == 1

    def test_malformed_arc_key_skipped(self):
        data = self._make_data("src/foo.py", {"bad_key": 1, "(1, 5)": 2})
        hits = parse_branch_hits(data, "src/foo.py")
        # Only the valid key is parsed
        assert len(hits) == 1

    def test_empty_arcs(self):
        data = self._make_data("src/foo.py", {})
        hits = parse_branch_hits(data, "src/foo.py")
        assert hits == []

    def test_no_files_key(self):
        result = parse_branch_hits({}, "src/foo.py")
        assert result == []


# ---------------------------------------------------------------------------
# parse_branch_hits — missing_branches fallback
# ---------------------------------------------------------------------------


class TestParseBranchHitsMissingBranches:
    def _make_data(self, file_path: str, missing_branches: list) -> dict:
        return {"files": {file_path: {"missing_branches": missing_branches}}}

    def test_missing_branches_get_hits_zero(self):
        data = self._make_data("src/bar.py", [[3, 5], [7, 9]])
        hits = parse_branch_hits(data, "src/bar.py")
        assert len(hits) == 2
        assert all(h.hits == 0 for h in hits)

    def test_branch_pairs_parsed(self):
        data = self._make_data("src/bar.py", [[10, 20]])
        hits = parse_branch_hits(data, "src/bar.py")
        assert hits[0].from_line == 10
        assert hits[0].to_line == 20

    def test_malformed_item_skipped(self):
        data = self._make_data("src/bar.py", [[1, 2], "bad", [3, 4]])
        hits = parse_branch_hits(data, "src/bar.py")
        assert len(hits) == 2

    def test_empty_missing_branches(self):
        data = self._make_data("src/bar.py", [])
        hits = parse_branch_hits(data, "src/bar.py")
        assert hits == []


# ---------------------------------------------------------------------------
# compute_branch_stats
# ---------------------------------------------------------------------------


class TestComputeBranchStats:
    def test_all_hit(self):
        hits = [BranchHit(1, 5, 3), BranchHit(1, 10, 1)]
        stats = compute_branch_stats("f.py", hits)
        assert stats.total_branches == 2
        assert stats.hit_branches == 2
        assert stats.miss_branches == 0
        assert stats.hit_rate == pytest.approx(1.0)

    def test_all_miss(self):
        hits = [BranchHit(1, 5, 0), BranchHit(1, 10, 0)]
        stats = compute_branch_stats("f.py", hits)
        assert stats.hit_branches == 0
        assert stats.miss_branches == 2
        assert stats.hit_rate == pytest.approx(0.0)

    def test_mixed(self):
        hits = [BranchHit(1, 5, 2), BranchHit(1, 10, 0), BranchHit(2, 6, 1)]
        stats = compute_branch_stats("f.py", hits)
        assert stats.hit_branches == 2
        assert stats.miss_branches == 1
        assert stats.hit_rate == pytest.approx(2 / 3)

    def test_empty_returns_full_hit_rate(self):
        stats = compute_branch_stats("f.py", [])
        assert stats.total_branches == 0
        assert stats.hit_rate == pytest.approx(1.0)

    def test_file_path_preserved(self):
        stats = compute_branch_stats("src/lidco/core/session.py", [])
        assert stats.file_path == "src/lidco/core/session.py"


# ---------------------------------------------------------------------------
# format_branch_stats
# ---------------------------------------------------------------------------


class TestFormatBranchStats:
    def test_contains_file_path(self):
        stats = BranchStats("src/foo.py", 10, 8, 2, 0.8)
        result = format_branch_stats(stats)
        assert "src/foo.py" in result

    def test_contains_counts(self):
        stats = BranchStats("f.py", 10, 7, 3, 0.7)
        result = format_branch_stats(stats)
        assert "10" in result
        assert "7" in result
        assert "3" in result

    def test_contains_percentage(self):
        stats = BranchStats("f.py", 4, 3, 1, 0.75)
        result = format_branch_stats(stats)
        assert "75" in result

    def test_markdown_header(self):
        stats = BranchStats("f.py", 0, 0, 0, 1.0)
        result = format_branch_stats(stats)
        assert "##" in result
