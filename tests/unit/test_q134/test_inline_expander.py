"""Tests for Q134 InlineExpander."""
from __future__ import annotations

import unittest

from lidco.transform.inline_expander import InlineExpander, InlineResult


class TestInlineResult(unittest.TestCase):
    def test_dataclass_fields(self):
        r = InlineResult(variable_name="x", value_expr="1", replacements=2, new_source="y = 1")
        self.assertEqual(r.variable_name, "x")
        self.assertEqual(r.value_expr, "1")
        self.assertEqual(r.replacements, 2)


class TestInlineExpander(unittest.TestCase):
    def setUp(self):
        self.inliner = InlineExpander()

    def test_inline_simple(self):
        src = "x = 42\ny = x + 1\n"
        result = self.inliner.inline_variable(src, "x")
        self.assertIn("42 + 1", result.new_source)
        self.assertGreaterEqual(result.replacements, 1)
        self.assertEqual(result.value_expr, "42")

    def test_inline_removes_assignment(self):
        src = "x = 42\ny = x + 1\n"
        result = self.inliner.inline_variable(src, "x")
        # The assignment line should be removed
        self.assertNotIn("x = 42", result.new_source)

    def test_inline_multiple_usages(self):
        src = "x = 10\na = x\nb = x\n"
        result = self.inliner.inline_variable(src, "x")
        self.assertEqual(result.replacements, 2)

    def test_inline_no_assignment(self):
        src = "print(x)\n"
        result = self.inliner.inline_variable(src, "x")
        self.assertEqual(result.replacements, 0)

    def test_inline_multiple_assignments(self):
        src = "x = 1\nx = 2\nprint(x)\n"
        result = self.inliner.inline_variable(src, "x")
        self.assertEqual(result.replacements, 0)

    def test_inline_syntax_error(self):
        result = self.inliner.inline_variable("def (", "x")
        self.assertEqual(result.replacements, 0)
        self.assertEqual(result.new_source, "def (")

    def test_inline_no_usages(self):
        src = "x = 42\ny = 1\n"
        result = self.inliner.inline_variable(src, "x")
        self.assertEqual(result.replacements, 0)

    def test_can_inline_simple(self):
        src = "x = 42\nprint(x)\n"
        self.assertTrue(self.inliner.can_inline(src, "x"))

    def test_can_inline_with_call(self):
        src = "x = foo()\nprint(x)\n"
        self.assertFalse(self.inliner.can_inline(src, "x"))

    def test_can_inline_multiple_assignments(self):
        src = "x = 1\nx = 2\n"
        self.assertFalse(self.inliner.can_inline(src, "x"))

    def test_can_inline_no_assignment(self):
        src = "print(x)\n"
        self.assertFalse(self.inliner.can_inline(src, "x"))

    def test_can_inline_syntax_error(self):
        self.assertFalse(self.inliner.can_inline("def (", "x"))

    def test_find_assignments_basic(self):
        src = "x = 42\ny = 10\n"
        assignments = self.inliner.find_assignments(src, "x")
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0][0], 1)
        self.assertEqual(assignments[0][1], "42")

    def test_find_assignments_multiple(self):
        src = "x = 1\nx = 2\n"
        assignments = self.inliner.find_assignments(src, "x")
        self.assertEqual(len(assignments), 2)

    def test_find_assignments_none(self):
        src = "print(x)\n"
        self.assertEqual(self.inliner.find_assignments(src, "x"), [])

    def test_find_assignments_syntax_error(self):
        self.assertEqual(self.inliner.find_assignments("def (", "x"), [])

    def test_inline_expression_value(self):
        src = "x = 2 + 3\ny = x * 2\n"
        result = self.inliner.inline_variable(src, "x")
        self.assertIn("2 + 3", result.new_source)

    def test_can_inline_string_value(self):
        src = 'name = "hello"\nprint(name)\n'
        self.assertTrue(self.inliner.can_inline(src, "name"))


if __name__ == "__main__":
    unittest.main()
