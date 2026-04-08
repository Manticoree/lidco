"""Tests for gitanalytics.velocity module."""

import unittest
from unittest.mock import patch, MagicMock

from lidco.gitanalytics.velocity import (
    VelocityAnalyzer,
    VelocityMetrics,
    CycleTimeMetrics,
)


_SAMPLE_LOG = """\
a1|Alice|alice@ex.com|2026-03-01T10:00:00+00:00
a2|Bob|bob@ex.com|2026-03-01T14:00:00+00:00
a3|Alice|alice@ex.com|2026-03-02T10:00:00+00:00
a4|Carol|carol@ex.com|2026-03-03T09:00:00+00:00
"""


class TestVelocityMetrics(unittest.TestCase):
    def test_frozen(self):
        m = VelocityMetrics(
            commits_per_day=1.0,
            active_days=1,
            total_commits=1,
            period_days=1,
            authors_active=1,
            avg_commits_per_author=1.0,
            busiest_day="2026-03-01",
            busiest_day_commits=1,
        )
        with self.assertRaises(AttributeError):
            m.total_commits = 5  # type: ignore[misc]


class TestCycleTimeMetrics(unittest.TestCase):
    def test_frozen(self):
        c = CycleTimeMetrics(
            avg_cycle_hours=0.0, median_cycle_hours=0.0, p90_cycle_hours=0.0, total_prs=0
        )
        with self.assertRaises(AttributeError):
            c.total_prs = 10  # type: ignore[misc]


class TestVelocityAnalyzer(unittest.TestCase):
    @patch("lidco.gitanalytics.velocity.subprocess.run")
    def test_compute_basic(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout=_SAMPLE_LOG)
        v = VelocityAnalyzer("/fake")
        m = v.compute(days=30)
        self.assertEqual(m.total_commits, 4)
        self.assertEqual(m.active_days, 3)
        self.assertEqual(m.authors_active, 3)
        self.assertGreater(m.commits_per_day, 0)
        self.assertEqual(m.busiest_day, "2026-03-01")
        self.assertEqual(m.busiest_day_commits, 2)

    @patch("lidco.gitanalytics.velocity.subprocess.run")
    def test_compute_empty(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout="")
        v = VelocityAnalyzer("/fake")
        m = v.compute(days=7)
        self.assertEqual(m.total_commits, 0)
        self.assertEqual(m.active_days, 0)
        self.assertEqual(m.commits_per_day, 0.0)
        self.assertEqual(m.busiest_day, "")

    @patch("lidco.gitanalytics.velocity.subprocess.run")
    def test_daily_breakdown(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout=_SAMPLE_LOG)
        v = VelocityAnalyzer("/fake")
        breakdown = v.daily_breakdown(days=7)
        self.assertEqual(len(breakdown), 7)
        for entry in breakdown:
            self.assertIn("date", entry)
            self.assertIn("commits", entry)

    def test_cycle_time_empty(self):
        v = VelocityAnalyzer("/fake")
        ct = v.cycle_time(merge_log=None)
        self.assertEqual(ct.total_prs, 0)
        self.assertEqual(ct.avg_cycle_hours, 0.0)

    def test_cycle_time_basic(self):
        v = VelocityAnalyzer("/fake")
        log = [
            {"opened": "2026-03-01T10:00:00", "merged": "2026-03-01T22:00:00"},
            {"opened": "2026-03-02T08:00:00", "merged": "2026-03-03T08:00:00"},
        ]
        ct = v.cycle_time(merge_log=log)
        self.assertEqual(ct.total_prs, 2)
        self.assertAlmostEqual(ct.avg_cycle_hours, 18.0, places=1)
        self.assertGreater(ct.median_cycle_hours, 0)

    def test_cycle_time_invalid_entries_skipped(self):
        v = VelocityAnalyzer("/fake")
        log = [
            {"opened": "bad-date", "merged": "also-bad"},
            {"opened": "2026-03-01T10:00:00", "merged": "2026-03-01T22:00:00"},
        ]
        ct = v.cycle_time(merge_log=log)
        self.assertEqual(ct.total_prs, 1)

    @patch("lidco.gitanalytics.velocity.subprocess.run")
    def test_compute_with_since(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout=_SAMPLE_LOG)
        v = VelocityAnalyzer("/fake")
        v.compute(days=30, since="2026-03-01")
        cmd = mock_run.call_args[0][0]
        self.assertIn("--since=2026-03-01", cmd)

    @patch("lidco.gitanalytics.velocity.subprocess.run")
    def test_timeout_returns_empty(self, mock_run: MagicMock):
        import subprocess as sp
        mock_run.side_effect = sp.TimeoutExpired(cmd="git", timeout=60)
        v = VelocityAnalyzer("/fake")
        m = v.compute(days=7)
        self.assertEqual(m.total_commits, 0)


if __name__ == "__main__":
    unittest.main()
