"""Tests for gitanalytics.churn_predictor module."""

import unittest
from unittest.mock import patch, MagicMock

from lidco.gitanalytics.churn_predictor import (
    ChurnEntry,
    ChurnPredictor,
    ChurnReport,
)


_SAMPLE_LOG = """\
abc1|2026-03-01T10:00:00+00:00
src/foo.py
src/bar.py

abc2|2026-03-02T10:00:00+00:00
src/foo.py
src/baz.py

abc3|2026-03-03T10:00:00+00:00
src/foo.py
src/bar.py

abc4|2026-03-04T10:00:00+00:00
src/foo.py
"""


class TestChurnEntry(unittest.TestCase):
    def test_frozen(self):
        e = ChurnEntry(path="a.py", score=1.0, change_count=3, last_changed="2026-01-01")
        with self.assertRaises(AttributeError):
            e.score = 0.0  # type: ignore[misc]

    def test_defaults(self):
        e = ChurnEntry(path="a.py", score=0.5, change_count=1, last_changed="x")
        self.assertEqual(e.coupled_files, [])


class TestChurnReport(unittest.TestCase):
    def test_frozen(self):
        r = ChurnReport(files=[], total_files_analyzed=0, period_days=30, threshold=0.0)
        with self.assertRaises(AttributeError):
            r.period_days = 60  # type: ignore[misc]


class TestChurnPredictor(unittest.TestCase):
    @patch("lidco.gitanalytics.churn_predictor.subprocess.run")
    def test_predict_basic(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout=_SAMPLE_LOG)
        cp = ChurnPredictor("/fake")
        report = cp.predict(days=30)

        self.assertGreater(len(report.files), 0)
        self.assertEqual(report.period_days, 30)
        # foo.py should be top — 4 changes
        top = report.files[0]
        self.assertEqual(top.path, "src/foo.py")
        self.assertEqual(top.change_count, 4)
        self.assertGreater(top.score, 0)

    @patch("lidco.gitanalytics.churn_predictor.subprocess.run")
    def test_predict_empty(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout="")
        cp = ChurnPredictor("/fake")
        report = cp.predict(days=30)
        self.assertEqual(len(report.files), 0)
        self.assertEqual(report.total_files_analyzed, 0)

    @patch("lidco.gitanalytics.churn_predictor.subprocess.run")
    def test_predict_top_n(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout=_SAMPLE_LOG)
        cp = ChurnPredictor("/fake")
        report = cp.predict(days=30, top_n=2)
        self.assertLessEqual(len(report.files), 2)

    @patch("lidco.gitanalytics.churn_predictor.subprocess.run")
    def test_predict_threshold(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout=_SAMPLE_LOG)
        cp = ChurnPredictor("/fake")
        report = cp.predict(days=30, threshold=999.0)
        self.assertEqual(len(report.files), 0)

    @patch("lidco.gitanalytics.churn_predictor.subprocess.run")
    def test_hot_spots(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout=_SAMPLE_LOG)
        cp = ChurnPredictor("/fake")
        spots = cp.hot_spots(days=30, top_n=2)
        self.assertLessEqual(len(spots), 2)
        self.assertEqual(spots[0].path, "src/foo.py")

    @patch("lidco.gitanalytics.churn_predictor.subprocess.run")
    def test_coupled_files(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout=_SAMPLE_LOG)
        cp = ChurnPredictor("/fake")
        coupled = cp.coupled_files("src/foo.py", days=30)
        # bar.py changes with foo.py in 2 commits
        self.assertIn("src/bar.py", coupled)

    @patch("lidco.gitanalytics.churn_predictor.subprocess.run")
    def test_coupled_files_unknown_path(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout=_SAMPLE_LOG)
        cp = ChurnPredictor("/fake")
        coupled = cp.coupled_files("nonexistent.py", days=30)
        self.assertEqual(coupled, [])

    @patch("lidco.gitanalytics.churn_predictor.subprocess.run")
    def test_timeout_returns_empty(self, mock_run: MagicMock):
        import subprocess as sp
        mock_run.side_effect = sp.TimeoutExpired(cmd="git", timeout=60)
        cp = ChurnPredictor("/fake")
        report = cp.predict(days=30)
        self.assertEqual(len(report.files), 0)

    @patch("lidco.gitanalytics.churn_predictor.subprocess.run")
    def test_score_recency_weighting(self, mock_run: MagicMock):
        """More recent changes should contribute higher score."""
        mock_run.return_value = MagicMock(stdout=_SAMPLE_LOG)
        cp = ChurnPredictor("/fake")
        report = cp.predict(days=90)
        # foo.py (4 changes) should score higher than bar.py (2 changes)
        scores = {f.path: f.score for f in report.files}
        self.assertGreater(scores.get("src/foo.py", 0), scores.get("src/bar.py", 0))


if __name__ == "__main__":
    unittest.main()
