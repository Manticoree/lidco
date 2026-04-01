"""Tests for REPLEnhancer."""
from __future__ import annotations

import unittest

from lidco.input.repl_enhance import REPLEnhancer


class TestIsMultilineInput(unittest.TestCase):
    def setUp(self):
        self.r = REPLEnhancer()

    def test_complete_line(self):
        self.assertFalse(self.r.is_multiline_input("x = 1"))

    def test_unclosed_paren(self):
        self.assertTrue(self.r.is_multiline_input("foo("))

    def test_unclosed_bracket(self):
        self.assertTrue(self.r.is_multiline_input("[1, 2,"))

    def test_unclosed_brace(self):
        self.assertTrue(self.r.is_multiline_input("{'a':"))

    def test_closed_brackets(self):
        self.assertFalse(self.r.is_multiline_input("foo(1, 2)"))

    def test_triple_quote_unterminated(self):
        self.assertTrue(self.r.is_multiline_input('"""hello'))

    def test_triple_quote_terminated(self):
        self.assertFalse(self.r.is_multiline_input('"""hello"""'))

    def test_disabled(self):
        r = REPLEnhancer(enable_multiline=False)
        self.assertFalse(r.is_multiline_input("foo("))

    def test_nested_brackets(self):
        self.assertFalse(self.r.is_multiline_input("foo([1, 2])"))
        self.assertTrue(self.r.is_multiline_input("foo([1, 2)"))


class TestAutoIndent(unittest.TestCase):
    def setUp(self):
        self.r = REPLEnhancer()

    def test_indent_after_colon(self):
        text = "def foo():\npass"
        result = self.r.auto_indent(text, 1)
        lines = result.split("\n")
        self.assertEqual(lines[1], "    pass")

    def test_preserve_existing_indent(self):
        text = "    if True:\nprint()"
        result = self.r.auto_indent(text, 1)
        lines = result.split("\n")
        self.assertEqual(lines[1], "        print()")

    def test_no_indent_without_colon(self):
        text = "x = 1\ny = 2"
        result = self.r.auto_indent(text, 1)
        lines = result.split("\n")
        self.assertEqual(lines[1], "y = 2")

    def test_cursor_line_zero(self):
        text = "hello\nworld"
        result = self.r.auto_indent(text, 0)
        self.assertEqual(result, text)

    def test_cursor_out_of_range(self):
        text = "hello"
        result = self.r.auto_indent(text, 5)
        self.assertEqual(result, text)


class TestMatchBracket(unittest.TestCase):
    def setUp(self):
        self.r = REPLEnhancer()

    def test_match_paren(self):
        self.assertEqual(self.r.match_bracket("(hello)", 0), 6)

    def test_match_closing_paren(self):
        self.assertEqual(self.r.match_bracket("(hello)", 6), 0)

    def test_match_bracket_square(self):
        self.assertEqual(self.r.match_bracket("[a, b]", 0), 5)

    def test_match_brace(self):
        self.assertEqual(self.r.match_bracket("{x}", 0), 2)

    def test_nested(self):
        self.assertEqual(self.r.match_bracket("((a))", 0), 4)
        self.assertEqual(self.r.match_bracket("((a))", 1), 3)

    def test_no_match(self):
        self.assertIsNone(self.r.match_bracket("(hello", 0))

    def test_non_bracket(self):
        self.assertIsNone(self.r.match_bracket("hello", 0))

    def test_out_of_range(self):
        self.assertIsNone(self.r.match_bracket("()", -1))
        self.assertIsNone(self.r.match_bracket("()", 10))


class TestHighlightSyntax(unittest.TestCase):
    def setUp(self):
        self.r = REPLEnhancer()

    def test_python_keyword_highlighted(self):
        result = self.r.highlight_syntax("def foo")
        self.assertIn("\033[1;34mdef\033[0m", result)
        self.assertIn("foo", result)

    def test_no_keywords(self):
        result = self.r.highlight_syntax("hello world")
        self.assertNotIn("\033[", result)

    def test_disabled(self):
        r = REPLEnhancer(enable_highlight=False)
        result = r.highlight_syntax("def foo")
        self.assertEqual(result, "def foo")

    def test_unknown_language(self):
        result = self.r.highlight_syntax("def foo", language="brainfuck")
        self.assertEqual(result, "def foo")

    def test_javascript_keywords(self):
        result = self.r.highlight_syntax("const x", language="javascript")
        self.assertIn("\033[1;34mconst\033[0m", result)


if __name__ == "__main__":
    unittest.main()
