"""Tests for SmellDashboard — Q254."""

from __future__ import annotations

import unittest

from lidco.smells.dashboard import SmellDashboard
from lidco.smells.scanner import SmellMatch


def _match(smell_id: str = "x", file: str = "a.py", line: int = 1,
           msg: str = "m", severity: str = "medium") -> SmellMatch:
    return SmellMatch(smell_id, file, line, msg, severity)


class TestBySeverity(unittest.TestCase):
    """by_severity aggregation."""

    def test_empty(self):
        d = SmellDashboard([])
        self.assertEqual(d.by_severity(), {})

    def test_counts(self):
        matches = [
            _match(severity="high"),
            _match(severity="high"),
            _match(severity="low"),
        ]
        d = SmellDashboard(matches)
        sev = d.by_severity()
        self.assertEqual(sev["high"], 2)
        self.assertEqual(sev["low"], 1)


class TestByFile(unittest.TestCase):
    """by_file aggregation."""

    def test_empty(self):
        d = SmellDashboard([])
        self.assertEqual(d.by_file(), {})

    def test_counts(self):
        matches = [
            _match(file="a.py"),
            _match(file="a.py"),
            _match(file="b.py"),
        ]
        d = SmellDashboard(matches)
        files = d.by_file()
        self.assertEqual(files["a.py"], 2)
        self.assertEqual(files["b.py"], 1)


class TestWorstFiles(unittest.TestCase):
    """worst_files ranking."""

    def test_empty(self):
        d = SmellDashboard([])
        self.assertEqual(d.worst_files(), [])

    def test_ranking(self):
        matches = [
            _match(file="a.py"),
            _match(file="b.py"),
            _match(file="b.py"),
            _match(file="b.py"),
            _match(file="a.py"),
        ]
        d = SmellDashboard(matches)
        worst = d.worst_files(limit=2)
        self.assertEqual(len(worst), 2)
        self.assertEqual(worst[0][0], "b.py")
        self.assertEqual(worst[0][1], 3)
        self.assertEqual(worst[1][0], "a.py")
        self.assertEqual(worst[1][1], 2)

    def test_limit(self):
        matches = [_match(file=f"f{i}.py") for i in range(20)]
        d = SmellDashboard(matches)
        self.assertEqual(len(d.worst_files(limit=5)), 5)


class TestImprovementScore(unittest.TestCase):
    """improvement_score calculation."""

    def test_no_smells_perfect(self):
        d = SmellDashboard([])
        self.assertEqual(d.improvement_score(), 100.0)

    def test_critical_heavy_penalty(self):
        matches = [_match(severity="critical")] * 10
        d = SmellDashboard(matches)
        self.assertEqual(d.improvement_score(), 0.0)

    def test_some_smells(self):
        matches = [_match(severity="low")] * 5  # penalty = 5
        d = SmellDashboard(matches)
        self.assertAlmostEqual(d.improvement_score(), 95.0)

    def test_floor_at_zero(self):
        matches = [_match(severity="high")] * 100  # penalty = 500
        d = SmellDashboard(matches)
        self.assertEqual(d.improvement_score(), 0.0)


class TestRender(unittest.TestCase):
    """render text dashboard."""

    def test_empty(self):
        d = SmellDashboard([])
        text = d.render()
        self.assertIn("Code Smell Dashboard", text)
        self.assertIn("Total smells: 0", text)
        self.assertIn("100.0/100", text)

    def test_with_matches(self):
        matches = [
            _match(file="a.py", severity="high"),
            _match(file="b.py", severity="medium"),
        ]
        d = SmellDashboard(matches)
        text = d.render()
        self.assertIn("Total smells: 2", text)
        self.assertIn("high", text)
        self.assertIn("medium", text)
        self.assertIn("Worst files", text)

    def test_unnamed_file(self):
        matches = [_match(file="")]
        d = SmellDashboard(matches)
        text = d.render()
        self.assertIn("<unnamed>", text)


if __name__ == "__main__":
    unittest.main()
