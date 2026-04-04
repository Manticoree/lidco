"""Tests for HookDashboard."""

import pytest

from lidco.githooks.dashboard import HookDashboard


class TestHookDashboard:
    def test_record_and_pass_rate_all_pass(self):
        d = HookDashboard()
        d.record_execution("lint", True, 0.5)
        d.record_execution("lint", True, 0.3)
        assert d.pass_rate("lint") == 1.0

    def test_pass_rate_mixed(self):
        d = HookDashboard()
        d.record_execution("lint", True, 0.1)
        d.record_execution("lint", False, 0.2)
        assert d.pass_rate("lint") == pytest.approx(0.5)

    def test_pass_rate_no_data(self):
        d = HookDashboard()
        assert d.pass_rate("unknown") == 0.0

    def test_avg_duration(self):
        d = HookDashboard()
        d.record_execution("test", True, 1.0)
        d.record_execution("test", True, 3.0)
        assert d.avg_duration("test") == pytest.approx(2.0)

    def test_avg_duration_no_data(self):
        d = HookDashboard()
        assert d.avg_duration("missing") == 0.0

    def test_most_failed_ranking(self):
        d = HookDashboard()
        d.record_execution("good", True, 0.1)
        d.record_execution("good", True, 0.1)
        d.record_execution("bad", False, 0.2)
        d.record_execution("bad", False, 0.3)
        d.record_execution("mid", False, 0.1)
        d.record_execution("mid", True, 0.1)
        ranked = d.most_failed(top_n=3)
        assert ranked[0]["hook"] == "bad"
        assert ranked[0]["failures"] == 2

    def test_most_failed_top_n(self):
        d = HookDashboard()
        for i in range(10):
            d.record_execution(f"hook-{i}", False, 0.1)
        assert len(d.most_failed(top_n=3)) == 3

    def test_most_failed_empty(self):
        d = HookDashboard()
        assert d.most_failed() == []

    def test_trends(self):
        d = HookDashboard()
        d.record_execution("lint", True, 0.5)
        d.record_execution("lint", False, 0.8)
        trends = d.trends("lint")
        assert len(trends) == 2
        assert trends[0]["passed"] is True
        assert trends[1]["passed"] is False
        assert "timestamp" in trends[0]
        assert "duration" in trends[0]

    def test_trends_empty(self):
        d = HookDashboard()
        assert d.trends("nope") == []

    def test_summary_empty(self):
        d = HookDashboard()
        s = d.summary()
        assert s["total_runs"] == 0
        assert s["total_pass"] == 0
        assert s["total_fail"] == 0
        assert s["overall_pass_rate"] == 0.0
        assert s["hooks_tracked"] == []

    def test_summary_with_data(self):
        d = HookDashboard()
        d.record_execution("lint", True, 0.1)
        d.record_execution("lint", False, 0.2)
        d.record_execution("test", True, 0.3)
        s = d.summary()
        assert s["total_runs"] == 3
        assert s["total_pass"] == 2
        assert s["total_fail"] == 1
        assert s["overall_pass_rate"] == pytest.approx(2 / 3)
        assert set(s["hooks_tracked"]) == {"lint", "test"}

    def test_record_multiple_hooks_isolated(self):
        d = HookDashboard()
        d.record_execution("a", True, 0.1)
        d.record_execution("b", False, 0.2)
        assert d.pass_rate("a") == 1.0
        assert d.pass_rate("b") == 0.0
