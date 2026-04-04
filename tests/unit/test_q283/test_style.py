"""Tests for lidco.adaptive.style — StyleTransfer."""
from __future__ import annotations

import unittest

from lidco.adaptive.style import StyleTransfer


class TestStyleTransfer(unittest.TestCase):
    def setUp(self):
        self.st = StyleTransfer()

    def test_detect_naming_snake_case(self):
        code = "my_variable = 1\nother_name = 2\nfoo_bar = 3"
        self.assertEqual(self.st.detect_naming(code), "snake_case")

    def test_detect_naming_camel_case(self):
        code = "myVariable = 1\notherName = 2\nfooBar = 3"
        self.assertEqual(self.st.detect_naming(code), "camelCase")

    def test_detect_naming_empty(self):
        self.assertEqual(self.st.detect_naming(""), "unknown")

    def test_analyze_returns_dict(self):
        code = "# comment\ndef my_func():\n    pass"
        result = self.st.analyze(code)
        self.assertIsInstance(result, dict)
        self.assertIn("naming", result)
        self.assertIn("comment_style", result)
        self.assertIn("indent", result)

    def test_analyze_hash_comments(self):
        code = "# this is a comment\nx = 1"
        result = self.st.analyze(code)
        self.assertEqual(result["comment_style"], "hash")

    def test_analyze_slash_comments(self):
        code = "// this is a comment\nvar x = 1;"
        result = self.st.analyze(code)
        self.assertEqual(result["comment_style"], "slash")

    def test_analyze_indent_spaces(self):
        code = "if True:\n    x = 1\n    y = 2"
        result = self.st.analyze(code)
        self.assertEqual(result["indent"], "spaces_4")

    def test_match_snake_to_snake(self):
        code = "my_var = 1"
        style = {"naming": "snake_case"}
        result = self.st.match(code, style)
        self.assertIn("my_var", result)

    def test_match_camel_to_snake(self):
        code = "myVariable = getValue()"
        style = {"naming": "snake_case"}
        result = self.st.match(code, style)
        self.assertIn("my_variable", result)
        self.assertIn("get_value", result)

    def test_match_snake_to_camel(self):
        code = "my_variable = get_value()"
        style = {"naming": "camelCase"}
        result = self.st.match(code, style)
        self.assertIn("myVariable", result)
        self.assertIn("getValue", result)

    def test_match_unknown_style_noop(self):
        code = "x = 1"
        result = self.st.match(code, {"naming": "unknown"})
        self.assertEqual(result, code)

    def test_analyze_blank_line_ratio(self):
        code = "a = 1\n\nb = 2\n\nc = 3"
        result = self.st.analyze(code)
        self.assertGreater(result["blank_line_ratio"], 0.0)


if __name__ == "__main__":
    unittest.main()
