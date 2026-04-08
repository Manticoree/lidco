"""Tests for gitanalytics.contributions module."""

import unittest
from unittest.mock import patch, MagicMock

from lidco.gitanalytics.contributions import (
    AuthorStats,
    ContributionAnalyzer,
    ContributionSummary,
)


_SAMPLE_LOG = """\
abc123|Alice|alice@ex.com|2026-03-01T10:00:00+00:00|feat: add feature
10\t5\tsrc/foo.py
3\t1\tsrc/bar.py

def456|Bob|bob@ex.com|2026-03-02T12:00:00+00:00|fix: review fix
2\t1\tsrc/foo.py

ghi789|Alice|alice@ex.com|2026-03-03T09:00:00+00:00|chore: cleanup
0\t20\tsrc/old.py
"""


class TestAuthorStats(unittest.TestCase):
    def test_frozen(self):
        s = AuthorStats(name="A", email="a@b.com", commits=1)
        with self.assertRaises(AttributeError):
            s.commits = 2  # type: ignore[misc]

    def test_defaults(self):
        s = AuthorStats(name="X", email="x@y.com")
        self.assertEqual(s.commits, 0)
        self.assertEqual(s.lines_added, 0)
        self.assertEqual(s.reviews, 0)


class TestContributionSummary(unittest.TestCase):
    def test_frozen(self):
        cs = ContributionSummary(
            total_commits=0, total_authors=0, authors=[], period_start="", period_end=""
        )
        with self.assertRaises(AttributeError):
            cs.total_commits = 5  # type: ignore[misc]


class TestContributionAnalyzer(unittest.TestCase):
    @patch("lidco.gitanalytics.contributions.subprocess.run")
    def test_analyze_basic(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout=_SAMPLE_LOG)
        analyzer = ContributionAnalyzer("/fake")
        summary = analyzer.analyze()

        self.assertEqual(summary.total_commits, 3)
        self.assertEqual(summary.total_authors, 2)
        # Alice has 2 commits, Bob has 1
        self.assertEqual(summary.authors[0].name, "Alice")
        self.assertEqual(summary.authors[0].commits, 2)
        self.assertEqual(summary.authors[0].lines_added, 13)
        self.assertEqual(summary.authors[0].lines_removed, 26)
        self.assertEqual(summary.authors[0].files_touched, 3)

        self.assertEqual(summary.authors[1].name, "Bob")
        self.assertEqual(summary.authors[1].commits, 1)

    @patch("lidco.gitanalytics.contributions.subprocess.run")
    def test_analyze_empty(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout="")
        analyzer = ContributionAnalyzer("/fake")
        summary = analyzer.analyze()
        self.assertEqual(summary.total_commits, 0)
        self.assertEqual(summary.total_authors, 0)
        self.assertEqual(summary.authors, [])

    @patch("lidco.gitanalytics.contributions.subprocess.run")
    def test_analyze_with_since(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout=_SAMPLE_LOG)
        analyzer = ContributionAnalyzer("/fake")
        analyzer.analyze(since="2026-03-01")
        cmd = mock_run.call_args[0][0]
        self.assertIn("--since=2026-03-01", cmd)

    @patch("lidco.gitanalytics.contributions.subprocess.run")
    def test_top_authors(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout=_SAMPLE_LOG)
        analyzer = ContributionAnalyzer("/fake")
        top = analyzer.top_authors(n=1)
        self.assertEqual(len(top), 1)
        self.assertEqual(top[0].name, "Alice")

    @patch("lidco.gitanalytics.contributions.subprocess.run")
    def test_review_detection(self, mock_run: MagicMock):
        log = "abc|Bob|bob@ex.com|2026-03-02|fix: review fix\n"
        mock_run.return_value = MagicMock(stdout=log)
        analyzer = ContributionAnalyzer("/fake")
        summary = analyzer.analyze()
        self.assertEqual(summary.authors[0].reviews, 1)

    @patch("lidco.gitanalytics.contributions.subprocess.run")
    def test_binary_numstat(self, mock_run: MagicMock):
        log = (
            "abc|A|a@b.com|2026-03-01|add img\n"
            "-\t-\timg.png\n"
        )
        mock_run.return_value = MagicMock(stdout=log)
        analyzer = ContributionAnalyzer("/fake")
        summary = analyzer.analyze()
        self.assertEqual(summary.authors[0].lines_added, 0)
        self.assertEqual(summary.authors[0].files_touched, 1)

    @patch("lidco.gitanalytics.contributions.subprocess.run")
    def test_timeout_returns_empty(self, mock_run: MagicMock):
        import subprocess as sp
        mock_run.side_effect = sp.TimeoutExpired(cmd="git", timeout=60)
        analyzer = ContributionAnalyzer("/fake")
        summary = analyzer.analyze()
        self.assertEqual(summary.total_commits, 0)

    @patch("lidco.gitanalytics.contributions.subprocess.run")
    def test_period_dates(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout=_SAMPLE_LOG)
        analyzer = ContributionAnalyzer("/fake")
        summary = analyzer.analyze()
        self.assertEqual(summary.period_start, "2026-03-01T10:00:00+00:00")
        self.assertEqual(summary.period_end, "2026-03-03T09:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
