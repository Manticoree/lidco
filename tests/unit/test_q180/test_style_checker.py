"""Tests for StyleConsistencyChecker."""

from __future__ import annotations

import unittest

from lidco.review.style_checker import (
    StyleConsistencyChecker,
    StyleReport,
    StyleViolation,
)


class TestStyleViolation(unittest.TestCase):
    def test_frozen(self) -> None:
        v = StyleViolation(rule="test", file="a.py", line=1, message="msg")
        with self.assertRaises(AttributeError):
            v.rule = "other"  # type: ignore[misc]

    def test_defaults(self) -> None:
        v = StyleViolation(rule="r", file="", line=1, message="m")
        self.assertEqual(v.severity, "warning")
        self.assertEqual(v.suggestion, "")


class TestStyleReport(unittest.TestCase):
    def test_empty(self) -> None:
        r = StyleReport()
        self.assertEqual(r.error_count, 0)
        self.assertEqual(r.warning_count, 0)
        self.assertIn("No style violations", r.format())

    def test_counts(self) -> None:
        r = StyleReport(violations=[
            StyleViolation("a", "f.py", 1, "m1", severity="error"),
            StyleViolation("b", "f.py", 2, "m2", severity="warning"),
            StyleViolation("c", "f.py", 3, "m3", severity="error"),
        ])
        self.assertEqual(r.error_count, 2)
        self.assertEqual(r.warning_count, 1)

    def test_format_with_suggestion(self) -> None:
        r = StyleReport(violations=[
            StyleViolation("r", "f.py", 1, "msg", suggestion="fix it"),
        ])
        text = r.format()
        self.assertIn("Suggestion: fix it", text)
        self.assertIn("f.py:1", text)


class TestStyleConsistencyChecker(unittest.TestCase):
    def setUp(self) -> None:
        self.checker = StyleConsistencyChecker()

    def test_clean_code(self) -> None:
        source = "def hello():\n    return 42\n"
        report = self.checker.check(source)
        errors = [v for v in report.violations if v.severity == "error"]
        self.assertEqual(errors, [])

    def test_trailing_whitespace(self) -> None:
        source = "x = 1   \n"
        report = self.checker.check(source)
        rules = [v.rule for v in report.violations]
        self.assertIn("trailing_whitespace", rules)

    def test_wildcard_import(self) -> None:
        source = "from os import *\n"
        report = self.checker.check(source)
        rules = [v.rule for v in report.violations]
        self.assertIn("wildcard_import", rules)
        severity = next(v.severity for v in report.violations if v.rule == "wildcard_import")
        self.assertEqual(severity, "error")

    def test_print_statement(self) -> None:
        source = "    print('debug')\n"
        report = self.checker.check(source)
        rules = [v.rule for v in report.violations]
        self.assertIn("print_statement", rules)

    def test_long_line(self) -> None:
        source = "x = " + "a" * 120 + "\n"
        report = self.checker.check(source)
        rules = [v.rule for v in report.violations]
        self.assertIn("long_line", rules)

    def test_todo_without_owner(self) -> None:
        source = "# TODO fix this\n"
        report = self.checker.check(source)
        rules = [v.rule for v in report.violations]
        self.assertIn("todo_without_owner", rules)

    def test_todo_with_owner_ok(self) -> None:
        source = "# TODO(john): fix this\n"
        report = self.checker.check(source)
        rules = [v.rule for v in report.violations]
        self.assertNotIn("todo_without_owner", rules)

    def test_custom_rules(self) -> None:
        checker = StyleConsistencyChecker(rules=[
            {"name": "no_foo", "pattern": r"\bfoo\b", "message": "No foo allowed", "severity": "error"},
        ])
        report = checker.check("x = foo()")
        self.assertEqual(len(report.violations), 1)
        self.assertEqual(report.violations[0].rule, "no_foo")

    def test_add_rule(self) -> None:
        checker = StyleConsistencyChecker(rules=[])
        checker.add_rule({"name": "test", "pattern": r"XXX", "message": "found", "severity": "info"})
        report = checker.check("XXX here")
        self.assertEqual(len(report.violations), 1)

    def test_invalid_regex_skipped(self) -> None:
        checker = StyleConsistencyChecker(rules=[
            {"name": "bad", "pattern": "[invalid", "message": "m"},
        ])
        report = checker.check("anything")
        self.assertEqual(len(report.violations), 0)

    def test_check_diff(self) -> None:
        diff = (
            "+++ b/module.py\n"
            "@@ -0,0 +1,3 @@\n"
            "+from os import *\n"
            "+x = 1\n"
        )
        report = self.checker.check_diff(diff)
        rules = [v.rule for v in report.violations]
        self.assertIn("wildcard_import", rules)

    def test_check_diff_ignores_removed_lines(self) -> None:
        diff = (
            "+++ b/module.py\n"
            "@@ -1,2 +1,2 @@\n"
            "-from os import *\n"
            "+import os\n"
        )
        report = self.checker.check_diff(diff)
        rules = [v.rule for v in report.violations]
        self.assertNotIn("wildcard_import", rules)

    def test_check_diff_line_numbers(self) -> None:
        diff = (
            "+++ b/module.py\n"
            "@@ -0,0 +10,2 @@\n"
            "+from os import *\n"
        )
        report = self.checker.check_diff(diff)
        for v in report.violations:
            if v.rule == "wildcard_import":
                self.assertEqual(v.line, 10)

    def test_filename_in_report(self) -> None:
        report = self.checker.check("from os import *", filename="test.py")
        self.assertTrue(any(v.file == "test.py" for v in report.violations))

    def test_learn_style_spaces(self) -> None:
        sources = ["    x = 1\n    y = 2\n", "    z = 3\n"]
        metrics = self.checker.learn_style(sources)
        self.assertEqual(metrics["indent_style"], "spaces")
        self.assertEqual(metrics["files_analyzed"], 2)

    def test_learn_style_tabs(self) -> None:
        sources = ["\tx = 1\n\ty = 2\n"]
        metrics = self.checker.learn_style(sources)
        self.assertEqual(metrics["indent_style"], "tabs")

    def test_learn_style_quotes(self) -> None:
        sources = ['x = "hello"\ny = "world"\n']
        metrics = self.checker.learn_style(sources)
        self.assertEqual(metrics["quote_style"], "double")

    def test_learn_style_empty(self) -> None:
        metrics = self.checker.learn_style([])
        self.assertEqual(metrics["files_analyzed"], 0)

    def test_rules_property(self) -> None:
        rules = self.checker.rules
        self.assertIsInstance(rules, list)
        self.assertTrue(len(rules) > 0)

    def test_tab_indentation(self) -> None:
        source = "\tx = 1\n"
        report = self.checker.check(source)
        rules = [v.rule for v in report.violations]
        self.assertIn("tabs_instead_of_spaces", rules)


if __name__ == "__main__":
    unittest.main()
