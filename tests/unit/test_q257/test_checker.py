"""Tests for lidco.types.checker — TypeCheckerIntegration."""
from __future__ import annotations

import unittest

from lidco.types.checker import CheckError, TypeCheckerIntegration


class TestCheckError(unittest.TestCase):
    def test_frozen(self):
        e = CheckError(file="a.py", line=1, message="err")
        with self.assertRaises(AttributeError):
            e.file = "b.py"  # type: ignore[misc]

    def test_defaults(self):
        e = CheckError(file="a.py", line=1, message="msg")
        self.assertEqual(e.severity, "error")
        self.assertEqual(e.code, "")


class TestParseMypyOutput(unittest.TestCase):
    def setUp(self):
        self.checker = TypeCheckerIntegration()

    def test_basic_error(self):
        out = 'src/foo.py:10: error: Incompatible types in assignment [assignment]'
        errors = self.checker.parse_mypy_output(out)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].file, "src/foo.py")
        self.assertEqual(errors[0].line, 10)
        self.assertEqual(errors[0].severity, "error")
        self.assertIn("Incompatible", errors[0].message)
        self.assertEqual(errors[0].code, "assignment")

    def test_warning(self):
        out = 'src/bar.py:5: warning: Unused import [unused-import]'
        errors = self.checker.parse_mypy_output(out)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].severity, "warning")

    def test_note(self):
        out = 'src/baz.py:1: note: See docs for help'
        errors = self.checker.parse_mypy_output(out)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].severity, "note")
        self.assertEqual(errors[0].code, "")

    def test_multiple_lines(self):
        out = (
            "a.py:1: error: Bad type [misc]\n"
            "b.py:2: error: Missing return [return]\n"
            "not a valid line\n"
        )
        errors = self.checker.parse_mypy_output(out)
        self.assertEqual(len(errors), 2)

    def test_empty_output(self):
        errors = self.checker.parse_mypy_output("")
        self.assertEqual(errors, [])


class TestParsePyrightOutput(unittest.TestCase):
    def setUp(self):
        self.checker = TypeCheckerIntegration()

    def test_basic_error(self):
        out = 'src/foo.py:10:5 - error: Cannot assign type "str" to "int" (reportGeneralClassIssues)'
        errors = self.checker.parse_pyright_output(out)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].file, "src/foo.py")
        self.assertEqual(errors[0].line, 10)
        self.assertEqual(errors[0].severity, "error")
        self.assertIn("Cannot assign", errors[0].message)
        self.assertEqual(errors[0].code, "reportGeneralClassIssues")

    def test_warning(self):
        out = 'src/bar.py:3:1 - warning: Variable is unused (reportUnusedVariable)'
        errors = self.checker.parse_pyright_output(out)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].severity, "warning")

    def test_information_becomes_note(self):
        out = 'src/baz.py:1:1 - information: Type info (reportInfo)'
        errors = self.checker.parse_pyright_output(out)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].severity, "note")

    def test_empty_output(self):
        errors = self.checker.parse_pyright_output("")
        self.assertEqual(errors, [])


class TestSuggestFix(unittest.TestCase):
    def setUp(self):
        self.checker = TypeCheckerIntegration()

    def test_incompatible_return(self):
        e = CheckError(file="a.py", line=1, message="Incompatible return value type")
        fix = self.checker.suggest_fix(e)
        self.assertIsNotNone(fix)
        self.assertIn("return", fix.lower())

    def test_incompatible_assignment(self):
        e = CheckError(file="a.py", line=1, message="Incompatible types in assignment")
        fix = self.checker.suggest_fix(e)
        self.assertIsNotNone(fix)

    def test_missing_return(self):
        e = CheckError(file="a.py", line=1, message="Missing return statement")
        fix = self.checker.suggest_fix(e)
        self.assertIsNotNone(fix)

    def test_has_no_attribute(self):
        e = CheckError(file="a.py", line=1, message='Module "foo" has no attribute "bar"')
        fix = self.checker.suggest_fix(e)
        self.assertIsNotNone(fix)

    def test_no_fix_for_unknown(self):
        e = CheckError(file="a.py", line=1, message="Something completely unknown xyzzy")
        fix = self.checker.suggest_fix(e)
        self.assertIsNone(fix)

    def test_could_be_none(self):
        e = CheckError(file="a.py", line=1, message='Value could be None')
        fix = self.checker.suggest_fix(e)
        self.assertIsNotNone(fix)
        self.assertIn("None", fix)


class TestSummary(unittest.TestCase):
    def setUp(self):
        self.checker = TypeCheckerIntegration()

    def test_no_errors(self):
        s = self.checker.summary([])
        self.assertIn("No type errors", s)

    def test_single_error(self):
        errors = [CheckError(file="a.py", line=1, message="err")]
        s = self.checker.summary(errors)
        self.assertIn("1 issue", s)
        self.assertIn("1 file", s)

    def test_multiple_files(self):
        errors = [
            CheckError(file="a.py", line=1, message="err1"),
            CheckError(file="b.py", line=2, message="err2"),
            CheckError(file="a.py", line=3, message="err3", severity="warning"),
        ]
        s = self.checker.summary(errors)
        self.assertIn("3 issue", s)
        self.assertIn("2 file", s)
        self.assertIn("error", s)
        self.assertIn("warning", s)


if __name__ == "__main__":
    unittest.main()
