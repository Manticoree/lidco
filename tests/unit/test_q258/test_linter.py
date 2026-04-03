"""Tests for DocLinter (Q258)."""
from __future__ import annotations

import unittest

from lidco.docgen.linter import DocLinter, LintIssue


class TestLintIssue(unittest.TestCase):
    def test_dataclass_fields(self):
        i = LintIssue(line=10, message="bad", severity="error", rule="r1")
        self.assertEqual(i.line, 10)
        self.assertEqual(i.message, "bad")
        self.assertEqual(i.severity, "error")
        self.assertEqual(i.rule, "r1")

    def test_frozen(self):
        i = LintIssue(line=1, message="x", severity="info", rule="r")
        with self.assertRaises(AttributeError):
            i.line = 2  # type: ignore[misc]


class TestLint(unittest.TestCase):
    def setUp(self):
        self.linter = DocLinter()

    def test_clean_source(self):
        src = 'def foo():\n    """Do foo."""\n    pass\n'
        issues = self.linter.lint(src)
        self.assertEqual(issues, [])

    def test_missing_docstring(self):
        src = "def foo():\n    pass\n"
        issues = self.linter.lint(src)
        rules = [i.rule for i in issues]
        self.assertIn("missing-docstring", rules)

    def test_private_not_flagged(self):
        src = "def _helper():\n    pass\n"
        issues = self.linter.lint(src)
        missing = [i for i in issues if i.rule == "missing-docstring"]
        self.assertEqual(missing, [])

    def test_class_missing_docstring(self):
        src = "class Foo:\n    pass\n"
        issues = self.linter.lint(src)
        rules = [i.rule for i in issues]
        self.assertIn("missing-docstring", rules)

    def test_sorted_by_line(self):
        src = "def z():\n    pass\ndef a():\n    pass\n"
        issues = self.linter.lint(src)
        lines = [i.line for i in issues]
        self.assertEqual(lines, sorted(lines))

    def test_syntax_error(self):
        with self.assertRaises(ValueError):
            self.linter.lint("def (broken")


class TestCheckParamMismatch(unittest.TestCase):
    def setUp(self):
        self.linter = DocLinter()

    def test_no_mismatch(self):
        src = 'def foo(x):\n    """Do foo.\n\n    x: the value\n    """\n    pass\n'
        issues = self.linter.check_param_mismatch(src)
        self.assertEqual(issues, [])

    def test_param_missing(self):
        src = 'def foo(x, y):\n    """Do foo.\n\n    x: the value\n    """\n    pass\n'
        issues = self.linter.check_param_mismatch(src)
        rules = [i.rule for i in issues]
        self.assertIn("param-missing", rules)
        msgs = " ".join(i.message for i in issues)
        self.assertIn("y", msgs)

    def test_param_extra(self):
        src = 'def foo(x):\n    """Do foo.\n\n    x: val\n    z: extra\n    """\n    pass\n'
        issues = self.linter.check_param_mismatch(src)
        rules = [i.rule for i in issues]
        self.assertIn("param-extra", rules)

    def test_self_excluded(self):
        src = (
            'class C:\n'
            '    def bar(self, a):\n'
            '        """Do bar.\n\n'
            '        a: thing\n'
            '        """\n'
            '        pass\n'
        )
        issues = self.linter.check_param_mismatch(src)
        self.assertEqual(issues, [])

    def test_sphinx_style(self):
        src = 'def foo(x):\n    """:param x: the val."""\n    pass\n'
        issues = self.linter.check_param_mismatch(src)
        missing = [i for i in issues if i.rule == "param-missing"]
        self.assertEqual(missing, [])


class TestCheckStyle(unittest.TestCase):
    def setUp(self):
        self.linter = DocLinter()

    def test_good_style(self):
        issues = self.linter.check_style("Do something useful.")
        self.assertEqual(issues, [])

    def test_empty_docstring(self):
        issues = self.linter.check_style("")
        rules = [i.rule for i in issues]
        self.assertIn("style-empty", rules)

    def test_lowercase_start(self):
        issues = self.linter.check_style("do something.")
        rules = [i.rule for i in issues]
        self.assertIn("style-capitalization", rules)

    def test_no_punctuation(self):
        issues = self.linter.check_style("Do something")
        rules = [i.rule for i in issues]
        self.assertIn("style-punctuation", rules)

    def test_multiline_no_blank(self):
        issues = self.linter.check_style("Summary.\nDetail here.")
        rules = [i.rule for i in issues]
        self.assertIn("style-blank-line", rules)

    def test_multiline_with_blank(self):
        issues = self.linter.check_style("Summary.\n\nDetail here.")
        rules = [i.rule for i in issues]
        self.assertNotIn("style-blank-line", rules)

    def test_question_mark_ok(self):
        issues = self.linter.check_style("Is it valid?")
        rules = [i.rule for i in issues]
        self.assertNotIn("style-punctuation", rules)


class TestCheckDeprecated(unittest.TestCase):
    def setUp(self):
        self.linter = DocLinter()

    def test_deprecated_without_notice(self):
        src = 'def old():\n    """Does old stuff."""\n    pass\n'
        issues = self.linter.check_deprecated(src, {"old"})
        rules = [i.rule for i in issues]
        self.assertIn("deprecated-undocumented", rules)

    def test_deprecated_with_notice(self):
        src = 'def old():\n    """Does old stuff.\n\n    .. deprecated:: Use new() instead.\n    """\n    pass\n'
        issues = self.linter.check_deprecated(src, {"old"})
        self.assertEqual(issues, [])

    def test_not_deprecated_ignored(self):
        src = 'def ok():\n    """Fine."""\n    pass\n'
        issues = self.linter.check_deprecated(src, {"old"})
        self.assertEqual(issues, [])

    def test_no_docstring_deprecated(self):
        src = "def old():\n    pass\n"
        issues = self.linter.check_deprecated(src, {"old"})
        rules = [i.rule for i in issues]
        self.assertIn("deprecated-undocumented", rules)


class TestSummary(unittest.TestCase):
    def setUp(self):
        self.linter = DocLinter()

    def test_no_issues(self):
        s = self.linter.summary([])
        self.assertIn("No documentation lint issues", s)

    def test_with_issues(self):
        issues = [
            LintIssue(line=1, message="a", severity="error", rule="r1"),
            LintIssue(line=2, message="b", severity="warning", rule="r2"),
            LintIssue(line=3, message="c", severity="error", rule="r3"),
        ]
        s = self.linter.summary(issues)
        self.assertIn("3 issue(s)", s)
        self.assertIn("error: 2", s)
        self.assertIn("warning: 1", s)


if __name__ == "__main__":
    unittest.main()
