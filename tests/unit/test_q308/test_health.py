"""Tests for gitanalytics.health module."""

import tempfile
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from lidco.gitanalytics.health import (
    HealthAnalyzer,
    HealthDimension,
    HealthReport,
)


class TestHealthDimension(unittest.TestCase):
    def test_frozen(self):
        d = HealthDimension(name="x", score=0.5, detail="ok")
        with self.assertRaises(AttributeError):
            d.score = 1.0  # type: ignore[misc]


class TestHealthReport(unittest.TestCase):
    def test_frozen(self):
        r = HealthReport(overall_score=0.8, grade="B", dimensions=[], recommendations=[])
        with self.assertRaises(AttributeError):
            r.grade = "A"  # type: ignore[misc]


class TestHealthAnalyzer(unittest.TestCase):
    def _mock_git(self, mock_run: MagicMock, log_lines: int = 30, shortlog: str = "", diff_stat_lines: int = 10):
        """Configure mock to return different outputs for different git commands."""
        def side_effect(cmd, **kwargs):
            result = MagicMock()
            if "shortlog" in cmd:
                result.stdout = shortlog or "\n".join(
                    f"  {i}\tAuthor{i}" for i in range(1, 4)
                )
            elif "--name-only" in cmd and "--format=" in cmd:
                result.stdout = "\n".join(f"file{i}.py" for i in range(diff_stat_lines))
            elif "--oneline" in cmd:
                result.stdout = "\n".join(f"abc{i} msg" for i in range(log_lines))
            else:
                result.stdout = ""
            return result
        mock_run.side_effect = side_effect

    @patch("lidco.gitanalytics.health.subprocess.run")
    def test_analyze_healthy_repo(self, mock_run: MagicMock):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "README.md").write_text("# Hello")
        (tmp / "tests").mkdir()
        try:
            self._mock_git(mock_run, log_lines=60, diff_stat_lines=10)
            h = HealthAnalyzer(str(tmp))
            report = h.analyze(days=30)

            self.assertGreater(report.overall_score, 0.5)
            self.assertIn(report.grade, ("A", "B", "C"))
            self.assertGreater(len(report.dimensions), 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @patch("lidco.gitanalytics.health.subprocess.run")
    def test_analyze_empty_repo(self, mock_run: MagicMock):
        tmp = Path(tempfile.mkdtemp())
        try:
            self._mock_git(mock_run, log_lines=0, shortlog="", diff_stat_lines=0)
            h = HealthAnalyzer(str(tmp))
            report = h.analyze(days=30)

            self.assertLessEqual(report.overall_score, 0.5)
            # Should have recommendations
            self.assertGreater(len(report.recommendations), 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @patch("lidco.gitanalytics.health.subprocess.run")
    def test_quick_score(self, mock_run: MagicMock):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "README.md").write_text("hi")
        (tmp / "tests").mkdir()
        try:
            self._mock_git(mock_run, log_lines=50)
            h = HealthAnalyzer(str(tmp))
            score = h.quick_score()
            self.assertIsInstance(score, float)
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @patch("lidco.gitanalytics.health.subprocess.run")
    def test_grade_a(self, mock_run: MagicMock):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "README.md").write_text("hi")
        (tmp / "tests").mkdir()
        try:
            self._mock_git(mock_run, log_lines=100, diff_stat_lines=5)
            # 5+ authors
            shortlog = "\n".join(f"  10\tDev{i}" for i in range(6))
            self._mock_git(mock_run, log_lines=100, shortlog=shortlog, diff_stat_lines=5)
            h = HealthAnalyzer(str(tmp))
            report = h.analyze()
            self.assertEqual(report.grade, "A")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @patch("lidco.gitanalytics.health.subprocess.run")
    def test_no_readme_recommendation(self, mock_run: MagicMock):
        tmp = Path(tempfile.mkdtemp())
        try:
            self._mock_git(mock_run, log_lines=10)
            h = HealthAnalyzer(str(tmp))
            report = h.analyze()
            readme_recs = [r for r in report.recommendations if "README" in r]
            self.assertGreater(len(readme_recs), 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @patch("lidco.gitanalytics.health.subprocess.run")
    def test_no_tests_recommendation(self, mock_run: MagicMock):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "README.md").write_text("hi")
        try:
            self._mock_git(mock_run, log_lines=10)
            h = HealthAnalyzer(str(tmp))
            report = h.analyze()
            test_recs = [r for r in report.recommendations if "test" in r.lower()]
            self.assertGreater(len(test_recs), 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @patch("lidco.gitanalytics.health.subprocess.run")
    def test_high_churn_warning(self, mock_run: MagicMock):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "README.md").write_text("hi")
        (tmp / "tests").mkdir()
        try:
            self._mock_git(mock_run, log_lines=50, diff_stat_lines=150)
            h = HealthAnalyzer(str(tmp))
            report = h.analyze()
            churn_dims = [d for d in report.dimensions if d.name == "file_churn"]
            self.assertEqual(len(churn_dims), 1)
            self.assertLess(churn_dims[0].score, 0.7)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @patch("lidco.gitanalytics.health.subprocess.run")
    def test_dimensions_cover_all_areas(self, mock_run: MagicMock):
        tmp = Path(tempfile.mkdtemp())
        try:
            self._mock_git(mock_run)
            h = HealthAnalyzer(str(tmp))
            report = h.analyze()
            names = {d.name for d in report.dimensions}
            self.assertIn("commit_activity", names)
            self.assertIn("author_diversity", names)
            self.assertIn("file_churn", names)
            self.assertIn("readme", names)
            self.assertIn("tests", names)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @patch("lidco.gitanalytics.health.subprocess.run")
    def test_timeout_still_produces_report(self, mock_run: MagicMock):
        import subprocess as sp
        mock_run.side_effect = sp.TimeoutExpired(cmd="git", timeout=60)
        tmp = Path(tempfile.mkdtemp())
        try:
            h = HealthAnalyzer(str(tmp))
            report = h.analyze()
            self.assertIsInstance(report, HealthReport)
            self.assertLessEqual(report.overall_score, 1.0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
