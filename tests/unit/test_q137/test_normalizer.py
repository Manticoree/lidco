"""Tests for Q137 TextNormalizer."""
from __future__ import annotations
import unittest
from lidco.text.normalizer import TextNormalizer, NormalizeResult


class TestNormalizeResult(unittest.TestCase):
    def test_fields(self):
        r = NormalizeResult(original="A", normalized="a", changes=["lowered"])
        self.assertEqual(r.original, "A")
        self.assertEqual(r.normalized, "a")
        self.assertEqual(r.changes, ["lowered"])

    def test_default_changes(self):
        r = NormalizeResult(original="a", normalized="a")
        self.assertEqual(r.changes, [])


class TestNormalize(unittest.TestCase):
    def setUp(self):
        self.n = TextNormalizer()

    def test_strip(self):
        r = self.n.normalize("  hi  ")
        self.assertEqual(r.normalized, "hi")
        self.assertIn("stripped", r.changes)

    def test_collapse_whitespace(self):
        r = self.n.normalize("a  b   c")
        self.assertEqual(r.normalized, "a b c")
        self.assertIn("collapsed_whitespace", r.changes)

    def test_lowercase(self):
        r = self.n.normalize("Hello")
        self.assertEqual(r.normalized, "hello")
        self.assertIn("lowered", r.changes)

    def test_no_changes(self):
        r = self.n.normalize("hello")
        self.assertEqual(r.changes, [])

    def test_all_changes(self):
        r = self.n.normalize("  Hello  World  ")
        self.assertEqual(r.normalized, "hello world")
        self.assertIn("stripped", r.changes)
        self.assertIn("collapsed_whitespace", r.changes)
        self.assertIn("lowered", r.changes)

    def test_original_preserved(self):
        r = self.n.normalize("  X  ")
        self.assertEqual(r.original, "  X  ")


class TestCollapseWhitespace(unittest.TestCase):
    def setUp(self):
        self.n = TextNormalizer()

    def test_multiple_spaces(self):
        self.assertEqual(self.n.collapse_whitespace("a  b"), "a b")

    def test_tabs_and_newlines(self):
        self.assertEqual(self.n.collapse_whitespace("a\t\nb"), "a b")

    def test_no_change(self):
        self.assertEqual(self.n.collapse_whitespace("a b"), "a b")

    def test_empty(self):
        self.assertEqual(self.n.collapse_whitespace(""), "")


class TestStripPunctuation(unittest.TestCase):
    def setUp(self):
        self.n = TextNormalizer()

    def test_removes_punctuation(self):
        self.assertEqual(self.n.strip_punctuation("hello, world!"), "hello world")

    def test_keeps_words(self):
        self.assertEqual(self.n.strip_punctuation("abc"), "abc")

    def test_empty(self):
        self.assertEqual(self.n.strip_punctuation(""), "")


class TestToSlug(unittest.TestCase):
    def setUp(self):
        self.n = TextNormalizer()

    def test_basic_slug(self):
        self.assertEqual(self.n.to_slug("Hello World"), "hello-world")

    def test_strips_special_chars(self):
        self.assertEqual(self.n.to_slug("Hello, World!"), "hello-world")

    def test_collapses_hyphens(self):
        self.assertEqual(self.n.to_slug("a - - b"), "a-b")

    def test_strips_leading_trailing_hyphens(self):
        self.assertEqual(self.n.to_slug("--hello--"), "hello")

    def test_empty(self):
        self.assertEqual(self.n.to_slug(""), "")

    def test_numbers_kept(self):
        self.assertEqual(self.n.to_slug("Item 42"), "item-42")


class TestTruncate(unittest.TestCase):
    def setUp(self):
        self.n = TextNormalizer()

    def test_no_truncation_needed(self):
        self.assertEqual(self.n.truncate("hi", 10), "hi")

    def test_truncates(self):
        result = self.n.truncate("hello world", 8)
        self.assertEqual(result, "hello...")

    def test_custom_suffix(self):
        result = self.n.truncate("hello world", 9, suffix="~")
        self.assertEqual(result, "hello wo~")

    def test_exact_length(self):
        self.assertEqual(self.n.truncate("abc", 3), "abc")


class TestRemoveHtmlTags(unittest.TestCase):
    def setUp(self):
        self.n = TextNormalizer()

    def test_strips_tags(self):
        self.assertEqual(self.n.remove_html_tags("<p>hello</p>"), "hello")

    def test_nested_tags(self):
        self.assertEqual(self.n.remove_html_tags("<div><b>hi</b></div>"), "hi")

    def test_no_tags(self):
        self.assertEqual(self.n.remove_html_tags("plain text"), "plain text")

    def test_empty(self):
        self.assertEqual(self.n.remove_html_tags(""), "")


if __name__ == "__main__":
    unittest.main()
