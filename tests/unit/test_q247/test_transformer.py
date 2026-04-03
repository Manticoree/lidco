"""Tests for lidco.response.transformer."""
from __future__ import annotations

import unittest

from lidco.response.transformer import ResponseTransformer


class TestResponseTransformer(unittest.TestCase):
    """Tests for ResponseTransformer."""

    def setUp(self) -> None:
        self.t = ResponseTransformer()

    # -- strip_redundant ---------------------------------------------------

    def test_strip_redundant_no_repeats(self) -> None:
        self.assertEqual(self.t.strip_redundant("hello world"), "hello world")

    def test_strip_redundant_adjacent(self) -> None:
        self.assertEqual(self.t.strip_redundant("yes yes yes"), "yes")

    def test_strip_redundant_case_insensitive(self) -> None:
        self.assertEqual(self.t.strip_redundant("OK ok Ok"), "OK")

    def test_strip_redundant_empty(self) -> None:
        self.assertEqual(self.t.strip_redundant(""), "")

    # -- format_code -------------------------------------------------------

    def test_format_code_tabs_to_spaces(self) -> None:
        text = "```python\n\tx = 1\n```"
        result = self.t.format_code(text)
        self.assertIn("    x = 1", result)
        self.assertNotIn("\t", result)

    def test_format_code_no_code_blocks(self) -> None:
        text = "No code here."
        self.assertEqual(self.t.format_code(text), text)

    def test_format_code_nested_tabs(self) -> None:
        text = "```python\n\t\tdeep\n```"
        result = self.t.format_code(text)
        self.assertIn("        deep", result)

    # -- deduplicate -------------------------------------------------------

    def test_deduplicate_no_dupes(self) -> None:
        text = "First.\n\nSecond."
        self.assertEqual(self.t.deduplicate(text), text)

    def test_deduplicate_consecutive(self) -> None:
        text = "Same.\n\nSame.\n\nDifferent."
        result = self.t.deduplicate(text)
        self.assertEqual(result, "Same.\n\nDifferent.")

    def test_deduplicate_empty(self) -> None:
        self.assertEqual(self.t.deduplicate(""), "")

    def test_deduplicate_single_paragraph(self) -> None:
        self.assertEqual(self.t.deduplicate("Just one."), "Just one.")

    # -- apply_rules -------------------------------------------------------

    def test_apply_rules_single(self) -> None:
        rules = [{"pattern": r"foo", "replacement": "bar"}]
        self.assertEqual(self.t.apply_rules("foo baz", rules), "bar baz")

    def test_apply_rules_multiple(self) -> None:
        rules = [
            {"pattern": r"a", "replacement": "b"},
            {"pattern": r"b", "replacement": "c"},
        ]
        self.assertEqual(self.t.apply_rules("a", rules), "c")

    def test_apply_rules_empty(self) -> None:
        self.assertEqual(self.t.apply_rules("text", []), "text")

    def test_apply_rules_regex(self) -> None:
        rules = [{"pattern": r"\d+", "replacement": "N"}]
        self.assertEqual(self.t.apply_rules("item 42", rules), "item N")

    # -- transform (convenience) -------------------------------------------

    def test_transform_combined(self) -> None:
        text = "hello hello\n\nworld\n\nworld"
        result = self.t.transform(text)
        self.assertNotIn("hello hello", result)
        # Deduplicate should collapse the two "world" paragraphs
        self.assertEqual(result.count("world"), 1)

    def test_transform_preserves_code(self) -> None:
        text = "```python\npass\n```"
        result = self.t.transform(text)
        self.assertIn("pass", result)


if __name__ == "__main__":
    unittest.main()
