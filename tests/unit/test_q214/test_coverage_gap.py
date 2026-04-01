"""Tests for test_intel.coverage_gap — CoverageGap, CoverageGapFinder."""
from __future__ import annotations

import unittest

from lidco.test_intel.coverage_gap import CoverageGap, CoverageGapFinder


class TestCoverageGap(unittest.TestCase):
    def test_frozen(self):
        g = CoverageGap(file="f.py", line=10)
        with self.assertRaises(AttributeError):
            g.file = "x"  # type: ignore[misc]

    def test_defaults(self):
        g = CoverageGap(file="f.py", line=1)
        self.assertEqual(g.branch, "")
        self.assertEqual(g.complexity, 0)
        self.assertEqual(g.suggested_test, "")

    def test_fields(self):
        g = CoverageGap(file="a.py", line=5, branch="5->7", complexity=3, suggested_test="test")
        self.assertEqual(g.file, "a.py")
        self.assertEqual(g.line, 5)
        self.assertEqual(g.branch, "5->7")
        self.assertEqual(g.complexity, 3)


class TestCoverageGapFinder(unittest.TestCase):
    def test_parse_coverage_basic(self):
        data = {
            "files": {
                "module.py": {
                    "missing_lines": [10, 20],
                    "missing_branches": [[10, 12]],
                    "complexity": {"10": 5},
                }
            }
        }
        finder = CoverageGapFinder()
        gaps = finder.parse_coverage(data)
        self.assertEqual(len(gaps), 2)
        self.assertEqual(gaps[0].file, "module.py")
        self.assertEqual(gaps[0].line, 10)
        self.assertEqual(gaps[0].branch, "10->12")
        self.assertEqual(gaps[0].complexity, 5)

    def test_parse_coverage_empty(self):
        finder = CoverageGapFinder()
        gaps = finder.parse_coverage({})
        self.assertEqual(gaps, [])

    def test_find_gaps(self):
        finder = CoverageGapFinder()
        covered = {1, 2, 3}
        total = {1, 2, 3, 4, 5}
        gaps = finder.find_gaps(covered, total, "f.py")
        self.assertEqual(len(gaps), 2)
        lines = {g.line for g in gaps}
        self.assertEqual(lines, {4, 5})

    def test_find_gaps_full_coverage(self):
        finder = CoverageGapFinder()
        gaps = finder.find_gaps({1, 2, 3}, {1, 2, 3})
        self.assertEqual(gaps, [])

    def test_prioritize(self):
        finder = CoverageGapFinder()
        gaps = [
            CoverageGap(file="a.py", line=1, complexity=1),
            CoverageGap(file="a.py", line=2, complexity=5),
            CoverageGap(file="a.py", line=3, complexity=3),
        ]
        ordered = finder.prioritize(gaps)
        self.assertEqual(ordered[0].complexity, 5)
        self.assertEqual(ordered[1].complexity, 3)
        self.assertEqual(ordered[2].complexity, 1)

    def test_suggest_test(self):
        finder = CoverageGapFinder()
        gap = CoverageGap(file="mod.py", line=10, branch="10->12")
        suggestion = finder.suggest_test(gap)
        self.assertIn("mod.py:10", suggestion)
        self.assertIn("Branch: 10->12", suggestion)
        self.assertIn("def test_cover_line_10", suggestion)

    def test_suggest_test_with_source(self):
        finder = CoverageGapFinder()
        gap = CoverageGap(file="m.py", line=2)
        source = "x = 1\nif x > 0:\n    pass\n"
        suggestion = finder.suggest_test(gap, source)
        self.assertIn("if x > 0", suggestion)

    def test_summary_empty(self):
        finder = CoverageGapFinder()
        self.assertEqual(finder.summary([]), "No coverage gaps found.")

    def test_summary_with_gaps(self):
        finder = CoverageGapFinder()
        gaps = [
            CoverageGap(file="a.py", line=1, complexity=3),
            CoverageGap(file="a.py", line=2),
            CoverageGap(file="b.py", line=5),
        ]
        summary = finder.summary(gaps)
        self.assertIn("Coverage Gaps: 3", summary)
        self.assertIn("a.py: 2 gaps", summary)
        self.assertIn("b.py: 1 gaps", summary)
        self.assertIn("High priority", summary)

    def test_summary_no_high_priority(self):
        finder = CoverageGapFinder()
        gaps = [CoverageGap(file="a.py", line=1)]
        summary = finder.summary(gaps)
        self.assertNotIn("High priority", summary)


if __name__ == "__main__":
    unittest.main()
