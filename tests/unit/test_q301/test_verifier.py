"""Tests for lidco.merge.verifier."""
from __future__ import annotations

import unittest

from lidco.merge.verifier import PostMergeVerifier, TestResult, VerifyResult


class TestVerifyResult(unittest.TestCase):
    def test_empty_passed(self):
        vr = VerifyResult(passed=True)
        self.assertEqual(vr.total_issues, 0)

    def test_total_issues(self):
        vr = VerifyResult(
            passed=False,
            missing_files=["a.py"],
            extra_files=["b.py", "c.py"],
            content_mismatches=["d.py"],
        )
        self.assertEqual(vr.total_issues, 4)


class TestTestResult(unittest.TestCase):
    def test_defaults(self):
        tr = TestResult(name="test_foo", passed=True)
        self.assertEqual(tr.duration_ms, 0.0)
        self.assertEqual(tr.error, "")


class TestPostMergeVerifier(unittest.TestCase):
    def setUp(self):
        self.v = PostMergeVerifier()

    def test_verify_clean(self):
        before = {"a.py": "print(1)\n"}
        after = {"a.py": "print(1)\n"}
        result = self.v.verify(before, after)
        self.assertTrue(result.passed)
        self.assertEqual(result.total_issues, 0)

    def test_verify_missing_file(self):
        before = {"a.py": "x", "b.py": "y"}
        after = {"a.py": "x"}
        result = self.v.verify(before, after)
        self.assertFalse(result.passed)
        self.assertIn("b.py", result.missing_files)

    def test_verify_extra_file(self):
        before = {"a.py": "x"}
        after = {"a.py": "x", "new.py": "z"}
        result = self.v.verify(before, after)
        self.assertTrue(result.passed)  # extra files don't fail
        self.assertIn("new.py", result.extra_files)
        self.assertGreater(len(result.warnings), 0)

    def test_verify_conflict_markers(self):
        before = {"a.py": "x"}
        after = {"a.py": "<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> branch\n"}
        result = self.v.verify(before, after)
        self.assertFalse(result.passed)
        self.assertIn("a.py", result.content_mismatches)

    def test_check_regressions_none(self):
        results = [TestResult("t1", True), TestResult("t2", True)]
        self.assertEqual(self.v.check_regressions(results), [])

    def test_check_regressions_found(self):
        results = [
            TestResult("t1", True),
            TestResult("t2", False, error="boom"),
            TestResult("t3", False, error="fail"),
        ]
        regs = self.v.check_regressions(results)
        self.assertEqual(regs, ["t2", "t3"])

    def test_compare_behavior_regression(self):
        before = [TestResult("t1", True), TestResult("t2", True)]
        after = [TestResult("t1", True), TestResult("t2", False)]
        comp = self.v.compare_behavior(before, after)
        self.assertEqual(comp["regression_count"], 1)
        self.assertIn("t2", comp["regressions"])

    def test_compare_behavior_improvement(self):
        before = [TestResult("t1", False)]
        after = [TestResult("t1", True)]
        comp = self.v.compare_behavior(before, after)
        self.assertEqual(comp["improvement_count"], 1)

    def test_compare_behavior_new_and_removed(self):
        before = [TestResult("old", True)]
        after = [TestResult("new", True)]
        comp = self.v.compare_behavior(before, after)
        self.assertIn("old", comp["removed_tests"])
        self.assertIn("new", comp["new_tests"])

    def test_report_pass(self):
        vr = VerifyResult(passed=True)
        report = self.v.report(vr, regressions=[])
        self.assertIn("PASS", report)
        self.assertIn("No regressions", report)

    def test_report_fail(self):
        vr = VerifyResult(passed=False, missing_files=["x.py"])
        report = self.v.report(vr, regressions=["test_foo"])
        self.assertIn("FAIL", report)
        self.assertIn("x.py", report)
        self.assertIn("test_foo", report)

    def test_report_no_regressions_arg(self):
        vr = VerifyResult(passed=True)
        report = self.v.report(vr)
        # regressions=None means no regression section
        self.assertNotIn("regression", report.lower())


if __name__ == "__main__":
    unittest.main()
