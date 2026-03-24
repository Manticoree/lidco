"""Tests for AIContributionTracker — T506."""
from __future__ import annotations

import pytest

from lidco.analytics.ai_contribution import (
    AIContributionTracker,
    ContributionRecord,
    ModuleMetrics,
)


class TestRecord:
    def test_record_stores_entry(self, tmp_path):
        db = tmp_path / "contrib.db"
        tracker = AIContributionTracker(db_path=db)
        rec = tracker.record("auth.py", lines_added=10, lines_removed=2, author="ai", session_id="s1")
        assert isinstance(rec, ContributionRecord)
        assert rec.file == "auth.py"
        assert rec.lines_added == 10
        assert rec.author == "ai"

    def test_db_persists_across_instances(self, tmp_path):
        db = tmp_path / "contrib.db"
        tracker1 = AIContributionTracker(db_path=db)
        tracker1.record("file.py", 5, 0, "ai", "s1")

        tracker2 = AIContributionTracker(db_path=db)
        metrics = tracker2.module_metrics("file.py")
        assert metrics.ai_lines == 5


class TestModuleMetrics:
    def test_correct_ratio(self, tmp_path):
        db = tmp_path / "contrib.db"
        tracker = AIContributionTracker(db_path=db)
        tracker.record("mod.py", 80, 0, "ai", "s1")
        tracker.record("mod.py", 20, 0, "human", "s1")
        m = tracker.module_metrics("mod.py")
        assert m.ai_lines == 80
        assert m.human_lines == 20
        assert abs(m.ai_ratio - 0.8) < 0.001

    def test_zero_lines_returns_zero_ratio(self, tmp_path):
        db = tmp_path / "contrib.db"
        tracker = AIContributionTracker(db_path=db)
        m = tracker.module_metrics("nonexistent.py")
        assert m.ai_ratio == 0.0
        assert m.ai_lines == 0
        assert m.human_lines == 0


class TestSessionSummary:
    def test_aggregates_correctly(self, tmp_path):
        db = tmp_path / "contrib.db"
        tracker = AIContributionTracker(db_path=db)
        tracker.record("a.py", 50, 0, "ai", "sess1")
        tracker.record("b.py", 30, 0, "ai", "sess1")
        tracker.record("c.py", 20, 0, "human", "sess1")
        summary = tracker.session_summary("sess1")
        assert summary["ai_lines_added"] == 80
        assert summary["human_lines_added"] == 20
        assert abs(summary["ai_ratio"] - 0.8) < 0.001

    def test_multiple_sessions_tracked_separately(self, tmp_path):
        db = tmp_path / "contrib.db"
        tracker = AIContributionTracker(db_path=db)
        tracker.record("a.py", 100, 0, "ai", "sess1")
        tracker.record("b.py", 50, 0, "human", "sess2")
        s1 = tracker.session_summary("sess1")
        s2 = tracker.session_summary("sess2")
        assert s1["ai_lines_added"] == 100
        assert s1["human_lines_added"] == 0
        assert s2["human_lines_added"] == 50
        assert s2["ai_lines_added"] == 0


class TestAllModules:
    def test_sorted_by_ratio_desc(self, tmp_path):
        db = tmp_path / "contrib.db"
        tracker = AIContributionTracker(db_path=db)
        # high_ai.py: 90% AI
        tracker.record("high_ai.py", 90, 0, "ai", "s1")
        tracker.record("high_ai.py", 10, 0, "human", "s1")
        # low_ai.py: 10% AI
        tracker.record("low_ai.py", 10, 0, "ai", "s1")
        tracker.record("low_ai.py", 90, 0, "human", "s1")

        modules = tracker.all_modules()
        assert len(modules) == 2
        assert modules[0].file == "high_ai.py"
        assert modules[1].file == "low_ai.py"


class TestDashboardData:
    def test_totals_correct(self, tmp_path):
        db = tmp_path / "contrib.db"
        tracker = AIContributionTracker(db_path=db)
        tracker.record("a.py", 60, 0, "ai", "s1")
        tracker.record("b.py", 40, 0, "human", "s1")
        data = tracker.dashboard_data()
        assert data["total_ai_lines"] == 60
        assert data["total_human_lines"] == 40
        assert abs(data["ai_ratio"] - 0.6) < 0.001
        assert "top_ai_modules" in data

    def test_top_ai_modules_limited_to_5(self, tmp_path):
        db = tmp_path / "contrib.db"
        tracker = AIContributionTracker(db_path=db)
        for i in range(10):
            tracker.record(f"mod{i}.py", 100, 0, "ai", "s1")
        data = tracker.dashboard_data()
        assert len(data["top_ai_modules"]) <= 5
