"""Tests for ChangePreview (Q146 task 864)."""
from __future__ import annotations

import unittest

from lidco.editing.change_preview import ChangePreview, PreviewLine


class TestPreviewLine(unittest.TestCase):
    def test_fields(self):
        pl = PreviewLine(line_number=1, content="hello", change_type="add")
        self.assertEqual(pl.line_number, 1)
        self.assertEqual(pl.content, "hello")
        self.assertEqual(pl.change_type, "add")


class TestChangePreview(unittest.TestCase):
    def setUp(self):
        self.cp = ChangePreview()

    def test_has_changes_true(self):
        self.assertTrue(self.cp.has_changes("a", "b"))

    def test_has_changes_false(self):
        self.assertFalse(self.cp.has_changes("same", "same"))

    def test_has_changes_empty(self):
        self.assertFalse(self.cp.has_changes("", ""))

    def test_stats_no_change(self):
        s = self.cp.stats("a\nb\n", "a\nb\n")
        self.assertEqual(s["additions"], 0)
        self.assertEqual(s["deletions"], 0)
        self.assertEqual(s["unchanged"], 2)

    def test_stats_additions(self):
        s = self.cp.stats("a\n", "a\nb\n")
        self.assertGreater(s["additions"], 0)

    def test_stats_deletions(self):
        s = self.cp.stats("a\nb\n", "a\n")
        self.assertGreater(s["deletions"], 0)

    def test_stats_replacement(self):
        s = self.cp.stats("old line\n", "new line\n")
        self.assertGreater(s["additions"], 0)
        self.assertGreater(s["deletions"], 0)

    def test_stats_empty_to_content(self):
        s = self.cp.stats("", "hello\nworld\n")
        self.assertGreater(s["additions"], 0)
        self.assertEqual(s["deletions"], 0)

    def test_stats_content_to_empty(self):
        s = self.cp.stats("hello\nworld\n", "")
        self.assertEqual(s["additions"], 0)
        self.assertGreater(s["deletions"], 0)

    def test_preview_returns_list(self):
        lines = self.cp.preview("a\n", "b\n")
        self.assertIsInstance(lines, list)
        self.assertTrue(all(isinstance(l, PreviewLine) for l in lines))

    def test_preview_add_line(self):
        lines = self.cp.preview("a\n", "a\nb\n")
        types = [l.change_type for l in lines]
        self.assertIn("add", types)

    def test_preview_remove_line(self):
        lines = self.cp.preview("a\nb\n", "a\n")
        types = [l.change_type for l in lines]
        self.assertIn("remove", types)

    def test_preview_context_lines(self):
        old = "1\n2\n3\n4\n5\n"
        new = "1\n2\nX\n4\n5\n"
        lines = self.cp.preview(old, new, context_lines=1)
        types = [l.change_type for l in lines]
        self.assertIn("context", types)

    def test_preview_identical(self):
        lines = self.cp.preview("same\n", "same\n")
        self.assertEqual(lines, [])

    def test_format_preview_add(self):
        lines = [PreviewLine(1, "hello", "add")]
        out = self.cp.format_preview(lines)
        self.assertIn("+ hello", out)

    def test_format_preview_remove(self):
        lines = [PreviewLine(1, "hello", "remove")]
        out = self.cp.format_preview(lines)
        self.assertIn("- hello", out)

    def test_format_preview_context(self):
        lines = [PreviewLine(1, "hello", "context")]
        out = self.cp.format_preview(lines)
        self.assertIn("  hello", out)

    def test_format_preview_empty(self):
        out = self.cp.format_preview([])
        self.assertEqual(out, "")

    def test_format_preview_mixed(self):
        lines = [
            PreviewLine(1, "old", "remove"),
            PreviewLine(1, "new", "add"),
            PreviewLine(2, "same", "context"),
        ]
        out = self.cp.format_preview(lines)
        self.assertIn("- old", out)
        self.assertIn("+ new", out)
        self.assertIn("  same", out)

    def test_stats_keys(self):
        s = self.cp.stats("a\n", "b\n")
        self.assertIn("additions", s)
        self.assertIn("deletions", s)
        self.assertIn("unchanged", s)


if __name__ == "__main__":
    unittest.main()
