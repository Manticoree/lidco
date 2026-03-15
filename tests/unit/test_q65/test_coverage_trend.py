"""Tests for CoverageTrendTracker and CoverageSnapshot — Q65 Task 440."""

from __future__ import annotations

import json
import pytest
from pathlib import Path


class TestCoverageSnapshot:
    def test_snapshot_fields(self):
        from lidco.analytics.coverage_trend import CoverageSnapshot
        snap = CoverageSnapshot(
            commit_hash="abc123",
            timestamp="2025-01-01T00:00:00Z",
            overall_pct=85.5,
            file_coverages={"src/foo.py": 90.0},
        )
        assert snap.commit_hash == "abc123"
        assert snap.overall_pct == 85.5

    def test_snapshot_default_file_coverages(self):
        from lidco.analytics.coverage_trend import CoverageSnapshot
        snap = CoverageSnapshot(commit_hash="x", timestamp="2025-01-01T00:00:00Z", overall_pct=80.0)
        assert snap.file_coverages == {}


class TestCoverageTrendTracker:
    def test_load_history_empty_when_no_file(self, tmp_path):
        from lidco.analytics.coverage_trend import CoverageTrendTracker
        tracker = CoverageTrendTracker(project_dir=tmp_path)
        history = tracker.load_history()
        assert history == []

    def test_record_and_load(self, tmp_path):
        from lidco.analytics.coverage_trend import CoverageTrendTracker, CoverageSnapshot
        tracker = CoverageTrendTracker(project_dir=tmp_path)
        snap = CoverageSnapshot(commit_hash="abc", timestamp="2025-01-01T00:00:00Z", overall_pct=75.0)
        tracker.record(snap)
        history = tracker.load_history()
        assert len(history) == 1
        assert history[0].commit_hash == "abc"

    def test_load_last_n(self, tmp_path):
        from lidco.analytics.coverage_trend import CoverageTrendTracker, CoverageSnapshot
        tracker = CoverageTrendTracker(project_dir=tmp_path)
        for i in range(10):
            tracker.record(CoverageSnapshot(commit_hash=f"c{i}", timestamp="2025-01-01T00:00:00Z", overall_pct=float(i * 10)))
        history = tracker.load_history(last_n=3)
        assert len(history) == 3

    def test_detect_regressions_empty(self, tmp_path):
        from lidco.analytics.coverage_trend import CoverageTrendTracker
        tracker = CoverageTrendTracker(project_dir=tmp_path)
        assert tracker.detect_regressions() == []

    def test_detect_regressions_finds_drop(self, tmp_path):
        from lidco.analytics.coverage_trend import CoverageTrendTracker, CoverageSnapshot
        tracker = CoverageTrendTracker(project_dir=tmp_path)
        snap1 = CoverageSnapshot(commit_hash="c1", timestamp="2025-01-01T00:00:00Z", overall_pct=80.0,
                                  file_coverages={"src/foo.py": 90.0})
        snap2 = CoverageSnapshot(commit_hash="c2", timestamp="2025-01-02T00:00:00Z", overall_pct=70.0,
                                  file_coverages={"src/foo.py": 60.0})
        tracker.record(snap1)
        tracker.record(snap2)
        regressions = tracker.detect_regressions(threshold=2.0)
        files = [f for f, _ in regressions]
        assert "src/foo.py" in files

    def test_trend_line_empty(self, tmp_path):
        from lidco.analytics.coverage_trend import CoverageTrendTracker
        tracker = CoverageTrendTracker(project_dir=tmp_path)
        assert tracker.trend_line() == ""

    def test_trend_line_returns_chars(self, tmp_path):
        from lidco.analytics.coverage_trend import CoverageTrendTracker, CoverageSnapshot, _SPARK_BLOCKS
        tracker = CoverageTrendTracker(project_dir=tmp_path)
        for i, v in enumerate([60.0, 65.0, 70.0, 75.0]):
            tracker.record(CoverageSnapshot(commit_hash=f"c{i}", timestamp="2025-01-01T00:00:00Z", overall_pct=v))
        trend = tracker.trend_line()
        assert len(trend) > 0
        for ch in trend:
            assert ch in _SPARK_BLOCKS

    def test_no_regression_when_coverage_improves(self, tmp_path):
        from lidco.analytics.coverage_trend import CoverageTrendTracker, CoverageSnapshot
        tracker = CoverageTrendTracker(project_dir=tmp_path)
        snap1 = CoverageSnapshot(commit_hash="c1", timestamp="2025-01-01T00:00:00Z", overall_pct=70.0,
                                  file_coverages={"src/foo.py": 70.0})
        snap2 = CoverageSnapshot(commit_hash="c2", timestamp="2025-01-02T00:00:00Z", overall_pct=80.0,
                                  file_coverages={"src/foo.py": 80.0})
        tracker.record(snap1)
        tracker.record(snap2)
        regressions = tracker.detect_regressions(threshold=2.0)
        assert regressions == []
