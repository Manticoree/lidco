"""Tests for ImpactHeatmap — file scoring and risk analysis."""
from __future__ import annotations

import unittest

from lidco.ui.impact_heatmap import (
    ImpactHeatmap,
    ImpactEntry,
    HeatmapResult,
    _count_changes,
    _estimate_complexity,
)


class TestImpactHeatmapBasic(unittest.TestCase):
    def setUp(self):
        self.heatmap = ImpactHeatmap()

    def test_empty_changes(self):
        result = self.heatmap.analyze({})
        self.assertEqual(len(result.entries), 0)
        self.assertEqual(result.total_score, 0.0)

    def test_single_file_no_change(self):
        result = self.heatmap.analyze({"a.py": ("hello", "hello")})
        self.assertEqual(len(result.entries), 1)
        self.assertEqual(result.entries[0].score, 0.0)
        self.assertEqual(result.entries[0].risk_level, "low")

    def test_single_file_with_change(self):
        result = self.heatmap.analyze({"a.py": ("old", "new")})
        self.assertEqual(len(result.entries), 1)
        self.assertGreater(result.entries[0].score, 0)

    def test_multiple_files_sorted_by_score(self):
        changes = {
            "small.py": ("a", "b"),
            "big.py": ("a\nb\nc\nd\ne", "x\ny\nz\nw\nv"),
        }
        result = self.heatmap.analyze(changes)
        self.assertEqual(len(result.entries), 2)
        self.assertGreaterEqual(result.entries[0].score, result.entries[1].score)

    def test_file_field(self):
        result = self.heatmap.analyze({"test.py": ("a", "b")})
        self.assertEqual(result.entries[0].file, "test.py")


class TestImpactHeatmapRisk(unittest.TestCase):
    def setUp(self):
        self.heatmap = ImpactHeatmap(high_threshold=50.0, medium_threshold=20.0)

    def test_low_risk(self):
        result = self.heatmap.analyze({"a.py": ("a", "b")})
        self.assertEqual(result.entries[0].risk_level, "low")

    def test_high_risk_many_changes(self):
        old = "\n".join(f"line{i}" for i in range(100))
        new = "\n".join(f"changed{i}" for i in range(100))
        result = self.heatmap.analyze({"big.py": (old, new)})
        self.assertEqual(result.entries[0].risk_level, "high")

    def test_high_risk_count(self):
        old = "\n".join(f"line{i}" for i in range(100))
        new = "\n".join(f"changed{i}" for i in range(100))
        result = self.heatmap.analyze({"big.py": (old, new)})
        self.assertEqual(result.high_risk_count, 1)

    def test_custom_thresholds(self):
        heatmap = ImpactHeatmap(high_threshold=5.0, medium_threshold=2.0)
        result = heatmap.analyze({"a.py": ("a\nb\nc", "x\ny\nz")})
        self.assertIn(result.entries[0].risk_level, ("high", "medium"))


class TestImpactHeatmapComplexity(unittest.TestCase):
    def setUp(self):
        self.heatmap = ImpactHeatmap()

    def test_complex_code_higher_score(self):
        simple = "x = 1"
        complex_code = (
            "if x:\n"
            "    for i in range(10):\n"
            "        try:\n"
            "            while True:\n"
            "                if y:\n"
            "                    pass\n"
            "        except:\n"
            "            pass\n"
        )
        r1 = self.heatmap.analyze({"simple.py": ("", simple)})
        r2 = self.heatmap.analyze({"complex.py": ("", complex_code)})
        # Complex code should have at least same score (more lines changed too)
        self.assertGreaterEqual(r2.entries[0].score, r1.entries[0].score)

    def test_empty_file_complexity(self):
        result = _estimate_complexity("")
        self.assertEqual(result, 1.0)

    def test_simple_file_complexity(self):
        result = _estimate_complexity("x = 1\ny = 2")
        self.assertGreaterEqual(result, 1.0)


class TestCountChanges(unittest.TestCase):
    def test_no_changes(self):
        self.assertEqual(_count_changes("a", "a"), 0)

    def test_one_add(self):
        count = _count_changes("a", "a\nb")
        self.assertEqual(count, 1)

    def test_one_remove(self):
        count = _count_changes("a\nb", "a")
        self.assertEqual(count, 1)

    def test_replacement(self):
        count = _count_changes("a", "b")
        self.assertEqual(count, 2)  # one remove + one add


class TestHeatmapResult(unittest.TestCase):
    def test_total_score(self):
        r = HeatmapResult(entries=[
            ImpactEntry("a.py", 10.0, "low"),
            ImpactEntry("b.py", 30.0, "medium"),
        ])
        self.assertEqual(r.total_score, 40.0)

    def test_high_risk_count_zero(self):
        r = HeatmapResult(entries=[ImpactEntry("a.py", 5.0, "low")])
        self.assertEqual(r.high_risk_count, 0)

    def test_high_risk_count_multiple(self):
        r = HeatmapResult(entries=[
            ImpactEntry("a.py", 60.0, "high"),
            ImpactEntry("b.py", 70.0, "high"),
        ])
        self.assertEqual(r.high_risk_count, 2)

    def test_empty_result(self):
        r = HeatmapResult()
        self.assertEqual(r.total_score, 0.0)
        self.assertEqual(r.high_risk_count, 0)


if __name__ == "__main__":
    unittest.main()
