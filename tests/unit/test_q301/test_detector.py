"""Tests for lidco.merge.detector."""
from __future__ import annotations

import unittest

from lidco.merge.detector import Conflict, ConflictDetector, Severity, SimulationResult


class TestConflictDataclass(unittest.TestCase):
    def test_frozen(self):
        c = Conflict(file_path="a.py", line_start=1, line_end=5, text_a="x", text_b="y")
        with self.assertRaises(AttributeError):
            c.file_path = "b.py"  # type: ignore[misc]

    def test_defaults(self):
        c = Conflict(file_path="f", line_start=0, line_end=0, text_a="", text_b="")
        self.assertEqual(c.base_text, "")
        self.assertEqual(c.severity, "medium")


class TestSeverityEnum(unittest.TestCase):
    def test_values(self):
        self.assertEqual(Severity.LOW.value, "low")
        self.assertEqual(Severity.CRITICAL.value, "critical")


class TestSimulationResult(unittest.TestCase):
    def test_empty(self):
        sr = SimulationResult()
        self.assertFalse(sr.has_conflicts)
        self.assertEqual(sr.total_conflicts, 0)

    def test_with_conflicts(self):
        c = Conflict(file_path="a.py", line_start=0, line_end=0, text_a="x", text_b="y")
        sr = SimulationResult(conflicts=[c], conflicting_files=["a.py"])
        self.assertTrue(sr.has_conflicts)
        self.assertEqual(sr.total_conflicts, 1)


class TestConflictDetector(unittest.TestCase):
    def setUp(self):
        self.det = ConflictDetector()

    def test_no_conflict_single_branch_change(self):
        base = {"f.py": "line1\n"}
        a = {"f.py": "line1\nline2\n"}
        b = {"f.py": "line1\n"}
        conflicts = self.det.detect(base, a, b)
        self.assertEqual(len(conflicts), 0)

    def test_conflict_both_branches_change_same_file(self):
        base = {"f.py": "original\n"}
        a = {"f.py": "change_a\n"}
        b = {"f.py": "change_b\n"}
        conflicts = self.det.detect(base, a, b)
        self.assertGreater(len(conflicts), 0)
        self.assertEqual(conflicts[0].file_path, "f.py")

    def test_predict_affected(self):
        result = self.det.predict_affected(
            ["a.py", "b.py", "c.py"],
            ["b.py", "c.py", "d.py"],
        )
        self.assertEqual(result, ["b.py", "c.py"])

    def test_predict_affected_no_overlap(self):
        result = self.det.predict_affected(["a.py"], ["b.py"])
        self.assertEqual(result, [])

    def test_severity_score_range(self):
        c = Conflict(file_path="f.py", line_start=0, line_end=0, text_a="a", text_b="b")
        score = self.det.severity_score(c)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_severity_score_identical_is_low(self):
        c = Conflict(file_path="f.py", line_start=0, line_end=0, text_a="same", text_b="same")
        score = self.det.severity_score(c)
        self.assertLess(score, 0.5)

    def test_severity_score_divergent_is_higher(self):
        c_low = Conflict(file_path="f.py", line_start=0, line_end=0, text_a="abc", text_b="abd")
        c_high = Conflict(
            file_path="f.py",
            line_start=0,
            line_end=49,
            text_a="x" * 1000,
            text_b="y" * 1000,
        )
        self.assertGreater(self.det.severity_score(c_high), self.det.severity_score(c_low))

    def test_simulate_merge_clean(self):
        base = {"f.py": "line\n"}
        a = {"f.py": "line\nA\n"}
        b = {"f.py": "line\n"}
        result = self.det.simulate_merge(a, b, base=base)
        self.assertFalse(result.has_conflicts)

    def test_simulate_merge_with_conflicts(self):
        base = {"f.py": "orig\n"}
        a = {"f.py": "change_a\n"}
        b = {"f.py": "change_b\n"}
        result = self.det.simulate_merge(a, b, base=base)
        self.assertTrue(result.has_conflicts)
        self.assertIn("f.py", result.conflicting_files)

    def test_simulate_merge_no_base(self):
        a = {"f.py": "a\n"}
        b = {"f.py": "b\n"}
        result = self.det.simulate_merge(a, b)
        # Both differ from empty base — conflict expected
        self.assertTrue(result.has_conflicts)


if __name__ == "__main__":
    unittest.main()
