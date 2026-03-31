"""Tests for PerfAntiPatternDetector."""

from __future__ import annotations

import unittest

from lidco.review.perf_detector import (
    PerfAntiPatternDetector,
    PerfIssue,
    PerfReport,
)


class TestPerfIssue(unittest.TestCase):
    def test_frozen(self) -> None:
        i = PerfIssue(rule="r", file="f.py", line=1, message="m")
        with self.assertRaises(AttributeError):
            i.rule = "x"  # type: ignore[misc]

    def test_defaults(self) -> None:
        i = PerfIssue(rule="r", file="", line=1, message="m")
        self.assertEqual(i.severity, "warning")
        self.assertEqual(i.suggestion, "")


class TestPerfReport(unittest.TestCase):
    def test_empty(self) -> None:
        r = PerfReport()
        self.assertEqual(r.total, 0)
        self.assertEqual(r.error_count, 0)
        self.assertEqual(r.warning_count, 0)
        self.assertIn("No performance issues", r.format())

    def test_counts(self) -> None:
        r = PerfReport(issues=[
            PerfIssue("a", "f.py", 1, "m1", severity="error"),
            PerfIssue("b", "f.py", 2, "m2", severity="warning"),
            PerfIssue("c", "f.py", 3, "m3", severity="error"),
        ])
        self.assertEqual(r.error_count, 2)
        self.assertEqual(r.warning_count, 1)
        self.assertEqual(r.total, 3)

    def test_format_with_suggestion(self) -> None:
        r = PerfReport(issues=[
            PerfIssue("r", "f.py", 1, "msg", suggestion="fix it"),
        ])
        text = r.format()
        self.assertIn("Suggestion: fix it", text)
        self.assertIn("f.py:1", text)


class TestPerfAntiPatternDetector(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = PerfAntiPatternDetector()

    def test_clean_code(self) -> None:
        source = "def hello():\n    return 42\n"
        report = self.detector.detect(source)
        self.assertEqual(report.total, 0)

    def test_n_plus_one(self) -> None:
        source = "for user in users:\n    db.execute('SELECT * FROM orders')\n"
        report = self.detector.detect(source)
        rules = [i.rule for i in report.issues]
        self.assertIn("n_plus_one", rules)

    def test_string_concat_in_loop(self) -> None:
        source = "for item in items:\n    result += 'x'\n"
        report = self.detector.detect(source)
        rules = [i.rule for i in report.issues]
        self.assertIn("string_concat_in_loop", rules)

    def test_list_comprehension_to_len(self) -> None:
        source = "count = len([x for x in items if x > 0])\n"
        report = self.detector.detect(source)
        rules = [i.rule for i in report.issues]
        self.assertIn("list_comprehension_to_len", rules)

    def test_missing_pagination(self) -> None:
        source = "all_users = db.fetch_all()\n"
        report = self.detector.detect(source)
        rules = [i.rule for i in report.issues]
        self.assertIn("missing_pagination", rules)

    def test_nested_loops(self) -> None:
        source = "for i in a:\n    for j in b:\n        pass\n"
        report = self.detector.detect(source)
        rules = [i.rule for i in report.issues]
        self.assertIn("nested_loop_quadratic", rules)

    def test_custom_rules(self) -> None:
        detector = PerfAntiPatternDetector(rules=[
            {"name": "no_sleep", "pattern": r"time\.sleep", "message": "No sleep", "severity": "warning"},
        ])
        report = detector.detect("time.sleep(5)")
        self.assertEqual(len(report.issues), 1)

    def test_add_rule(self) -> None:
        detector = PerfAntiPatternDetector(rules=[])
        detector.add_rule({"name": "test", "pattern": r"SLOW", "message": "found"})
        report = detector.detect("SLOW operation")
        self.assertEqual(len(report.issues), 1)

    def test_invalid_regex_skipped(self) -> None:
        detector = PerfAntiPatternDetector(rules=[
            {"name": "bad", "pattern": "[invalid", "message": "m"},
        ])
        report = detector.detect("anything")
        self.assertEqual(report.total, 0)

    def test_rules_property(self) -> None:
        rules = self.detector.rules
        self.assertIsInstance(rules, list)
        self.assertTrue(len(rules) > 0)

    def test_detect_diff(self) -> None:
        diff = (
            "+++ b/module.py\n"
            "@@ -0,0 +1,2 @@\n"
            "+count = len([x for x in items if x > 0])\n"
            "+y = 1\n"
        )
        report = self.detector.detect_diff(diff)
        rules = [i.rule for i in report.issues]
        self.assertIn("list_comprehension_to_len", rules)

    def test_detect_diff_ignores_removed(self) -> None:
        diff = (
            "+++ b/module.py\n"
            "@@ -1,1 +1,1 @@\n"
            "-count = len([x for x in items if x > 0])\n"
            "+count = sum(1 for x in items if x > 0)\n"
        )
        report = self.detector.detect_diff(diff)
        rules = [i.rule for i in report.issues]
        self.assertNotIn("list_comprehension_to_len", rules)

    def test_filename_in_issues(self) -> None:
        report = self.detector.detect("count = len([x for x in items if x > 0])", filename="app.py")
        self.assertTrue(any(i.file == "app.py" for i in report.issues))

    def test_detect_diff_multiline(self) -> None:
        diff = (
            "+++ b/module.py\n"
            "@@ -0,0 +1,3 @@\n"
            "+for user in users:\n"
            "+    db.execute('SELECT * FROM orders')\n"
            "+    pass\n"
        )
        report = self.detector.detect_diff(diff)
        rules = [i.rule for i in report.issues]
        self.assertIn("n_plus_one", rules)

    def test_empty_diff(self) -> None:
        report = self.detector.detect_diff("")
        self.assertEqual(report.total, 0)


if __name__ == "__main__":
    unittest.main()
