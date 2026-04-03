"""Tests for FillInMiddle (Q251)."""
from __future__ import annotations

import unittest

from lidco.completion.fim import FillInMiddle


class TestFill(unittest.TestCase):
    def test_empty_both(self):
        fim = FillInMiddle()
        self.assertEqual(fim.fill("", ""), "")

    def test_function_def_prefix(self):
        fim = FillInMiddle()
        result = fim.fill("def foo():", "")
        self.assertEqual(result, "pass")

    def test_function_def_with_return_type(self):
        fim = FillInMiddle()
        result = fim.fill("def foo() -> int:", "")
        self.assertEqual(result, "pass")

    def test_if_prefix(self):
        fim = FillInMiddle()
        result = fim.fill("if x > 0:", "")
        self.assertEqual(result, "pass")

    def test_elif_prefix(self):
        fim = FillInMiddle()
        result = fim.fill("elif x < 0:", "")
        self.assertEqual(result, "pass")

    def test_else_prefix(self):
        fim = FillInMiddle()
        result = fim.fill("else:", "")
        self.assertEqual(result, "pass")

    def test_class_prefix(self):
        fim = FillInMiddle()
        result = fim.fill("class Foo:", "")
        self.assertIn("pass", result)

    def test_closing_bracket_suffix(self):
        fim = FillInMiddle()
        result = fim.fill("some_call(", ")")
        self.assertEqual(result, "")

    def test_closing_square_bracket(self):
        fim = FillInMiddle()
        result = fim.fill("items[", "]")
        self.assertEqual(result, "")

    def test_generic_fallback(self):
        fim = FillInMiddle()
        result = fim.fill("x = ", "")
        self.assertIn("TODO", result)

    def test_indent_applied(self):
        fim = FillInMiddle()
        result = fim.fill("x = ", "", indent="    ")
        self.assertTrue(result.startswith("    "))

    def test_indent_with_function(self):
        fim = FillInMiddle()
        result = fim.fill("def foo():", "", indent="    ")
        self.assertEqual(result, "    pass")


class TestDetectIndent(unittest.TestCase):
    def test_spaces(self):
        fim = FillInMiddle()
        text = "def foo():\n    return 1"
        self.assertEqual(fim.detect_indent(text), "    ")

    def test_tabs(self):
        fim = FillInMiddle()
        text = "def foo():\n\treturn 1"
        self.assertEqual(fim.detect_indent(text), "\t")

    def test_no_indent(self):
        fim = FillInMiddle()
        text = "x = 1\ny = 2"
        self.assertEqual(fim.detect_indent(text), "")

    def test_empty_string(self):
        fim = FillInMiddle()
        self.assertEqual(fim.detect_indent(""), "")


class TestSuggest(unittest.TestCase):
    def test_returns_multiple(self):
        fim = FillInMiddle()
        suggestions = fim.suggest("if x:", "")
        self.assertGreaterEqual(len(suggestions), 2)

    def test_first_is_fill(self):
        fim = FillInMiddle()
        suggestions = fim.suggest("if x:", "")
        self.assertEqual(suggestions[0], fim.fill("if x:", ""))

    def test_empty_returns_empty(self):
        fim = FillInMiddle()
        self.assertEqual(fim.suggest("", ""), [])


class TestSupportsMultiline(unittest.TestCase):
    def test_default_true(self):
        fim = FillInMiddle()
        self.assertTrue(fim.supports_multiline)


if __name__ == "__main__":
    unittest.main()
