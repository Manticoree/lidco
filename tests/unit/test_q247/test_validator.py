"""Tests for lidco.response.validator."""
from __future__ import annotations

import unittest

from lidco.response.validator import ResponseValidator, ValidationResult


class TestValidationResult(unittest.TestCase):
    """Tests for the ValidationResult dataclass."""

    def test_defaults(self) -> None:
        vr = ValidationResult(is_valid=True)
        self.assertTrue(vr.is_valid)
        self.assertEqual(vr.issues, [])

    def test_frozen(self) -> None:
        vr = ValidationResult(is_valid=True)
        with self.assertRaises(AttributeError):
            vr.is_valid = False  # type: ignore[misc]


class TestResponseValidator(unittest.TestCase):
    """Tests for ResponseValidator."""

    def setUp(self) -> None:
        self.v = ResponseValidator()

    # -- check_completeness ------------------------------------------------

    def test_complete_period(self) -> None:
        self.assertTrue(self.v.check_completeness("Done."))

    def test_complete_question(self) -> None:
        self.assertTrue(self.v.check_completeness("Is it done?"))

    def test_complete_exclamation(self) -> None:
        self.assertTrue(self.v.check_completeness("Done!"))

    def test_complete_backtick(self) -> None:
        self.assertTrue(self.v.check_completeness("Use `foo`"))

    def test_incomplete_empty(self) -> None:
        self.assertFalse(self.v.check_completeness(""))

    def test_incomplete_trailing_word(self) -> None:
        self.assertFalse(self.v.check_completeness("The answer is"))

    def test_incomplete_odd_fences(self) -> None:
        self.assertFalse(self.v.check_completeness("```python\ncode"))

    # -- check_code_syntax -------------------------------------------------

    def test_syntax_ok(self) -> None:
        issues = self.v.check_code_syntax("print('hello')")
        self.assertEqual(issues, [])

    def test_mismatched_parens(self) -> None:
        issues = self.v.check_code_syntax("print('hello'")
        self.assertTrue(any("(" in i for i in issues))

    def test_mismatched_brackets(self) -> None:
        issues = self.v.check_code_syntax("[1, 2, 3")
        self.assertTrue(any("[" in i for i in issues))

    def test_mismatched_braces(self) -> None:
        issues = self.v.check_code_syntax("{a: 1")
        self.assertTrue(any("{" in i for i in issues))

    def test_unmatched_quote(self) -> None:
        issues = self.v.check_code_syntax("x = 'hello")
        self.assertTrue(any("quote" in i.lower() for i in issues))

    def test_escaped_quotes_ok(self) -> None:
        issues = self.v.check_code_syntax("x = 'it\\'s fine'")
        self.assertEqual(issues, [])

    # -- detect_hallucinated_files -----------------------------------------

    def test_no_hallucination(self) -> None:
        known = {"/src/main.py"}
        result = self.v.detect_hallucinated_files(
            "See /src/main.py for details.", known,
        )
        self.assertEqual(result, [])

    def test_hallucinated_file(self) -> None:
        known: set[str] = set()
        result = self.v.detect_hallucinated_files(
            "Edit /src/fake/module.py now.", known,
        )
        self.assertGreater(len(result), 0)

    # -- validate ----------------------------------------------------------

    def test_validate_valid(self) -> None:
        r = self.v.validate("Everything is fine.")
        self.assertTrue(r.is_valid)
        self.assertEqual(r.issues, [])

    def test_validate_incomplete(self) -> None:
        r = self.v.validate("The answer is")
        self.assertFalse(r.is_valid)
        self.assertTrue(any("incomplete" in i.lower() for i in r.issues))


if __name__ == "__main__":
    unittest.main()
