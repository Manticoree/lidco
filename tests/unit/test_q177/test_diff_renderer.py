"""Tests for DiffRenderer — unified, side-by-side, word-level, folding."""
from __future__ import annotations

import unittest

from lidco.ui.diff_renderer import DiffRenderer, WordDiff, _word_level_diff, _fold_unchanged


class TestDiffRendererUnified(unittest.TestCase):
    def setUp(self):
        self.renderer = DiffRenderer(context_lines=3)

    def test_identical_texts_returns_empty(self):
        result = self.renderer.render_unified("hello\n", "hello\n")
        self.assertEqual(result, "")

    def test_empty_old_text(self):
        result = self.renderer.render_unified("", "line1\nline2\n")
        self.assertIn("+", result)

    def test_empty_new_text(self):
        result = self.renderer.render_unified("line1\nline2\n", "")
        self.assertIn("-", result)

    def test_both_empty(self):
        result = self.renderer.render_unified("", "")
        self.assertEqual(result, "")

    def test_simple_addition(self):
        old = "a\nb\n"
        new = "a\nb\nc\n"
        result = self.renderer.render_unified(old, new)
        self.assertIn("+c", result)

    def test_simple_removal(self):
        old = "a\nb\nc\n"
        new = "a\nb\n"
        result = self.renderer.render_unified(old, new)
        self.assertIn("-c", result)

    def test_modification(self):
        old = "hello world\n"
        new = "hello python\n"
        result = self.renderer.render_unified(old, new)
        self.assertIn("-hello world", result)
        self.assertIn("+hello python", result)

    def test_filename_in_header(self):
        result = self.renderer.render_unified("a\n", "b\n", filename="test.py")
        self.assertIn("a/test.py", result)
        self.assertIn("b/test.py", result)

    def test_no_filename_default_header(self):
        result = self.renderer.render_unified("a\n", "b\n")
        self.assertIn("a/old", result)
        self.assertIn("b/new", result)

    def test_multiline_changes(self):
        old = "line1\nline2\nline3\nline4\n"
        new = "line1\nchanged\nline3\nline4\n"
        result = self.renderer.render_unified(old, new)
        self.assertIn("-line2", result)
        self.assertIn("+changed", result)


class TestDiffRendererSideBySide(unittest.TestCase):
    def setUp(self):
        self.renderer = DiffRenderer()

    def test_identical_texts(self):
        result = self.renderer.render_side_by_side("a\nb", "a\nb", width=80)
        self.assertIn("OLD", result)
        self.assertIn("NEW", result)
        self.assertIn("a", result)

    def test_added_line(self):
        result = self.renderer.render_side_by_side("a", "a\nb", width=80)
        self.assertIn("b", result)

    def test_removed_line(self):
        result = self.renderer.render_side_by_side("a\nb", "a", width=80)
        lines = result.split("\n")
        # Should have header + separator + content
        self.assertGreater(len(lines), 2)

    def test_replaced_line(self):
        result = self.renderer.render_side_by_side("old", "new", width=80)
        self.assertIn("old", result)
        self.assertIn("new", result)

    def test_custom_width(self):
        result = self.renderer.render_side_by_side("a", "b", width=40)
        lines = result.split("\n")
        # Each line should fit within width
        for line in lines:
            self.assertLessEqual(len(line), 42)  # small tolerance

    def test_empty_both(self):
        result = self.renderer.render_side_by_side("", "", width=80)
        self.assertIn("OLD", result)


class TestWordDiff(unittest.TestCase):
    def test_identical_lines(self):
        result = _word_level_diff("hello world", "hello world")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].kind, "equal")

    def test_word_added(self):
        result = _word_level_diff("hello", "hello world")
        kinds = [w.kind for w in result]
        self.assertIn("add", kinds)

    def test_word_removed(self):
        result = _word_level_diff("hello world", "hello")
        kinds = [w.kind for w in result]
        self.assertIn("remove", kinds)

    def test_word_replaced(self):
        result = _word_level_diff("hello world", "hello python")
        kinds = [w.kind for w in result]
        self.assertIn("remove", kinds)
        self.assertIn("add", kinds)

    def test_render_word_diff(self):
        renderer = DiffRenderer()
        result = renderer.render_word_diff("hello world", "hello python")
        self.assertIn("{+python+}", result)
        self.assertIn("[-world-]", result)

    def test_empty_lines(self):
        result = _word_level_diff("", "")
        self.assertEqual(len(result), 0)


class TestFolding(unittest.TestCase):
    def test_no_changes_returns_all(self):
        lines = ["  context1", "  context2", "  context3"]
        result = _fold_unchanged(lines, context=3)
        self.assertEqual(result, lines)

    def test_fold_large_unchanged(self):
        lines = ["+added"] + [f"  line{i}" for i in range(20)] + ["-removed"]
        result = _fold_unchanged(lines, context=2)
        self.assertTrue(any("folded" in l for l in result))

    def test_negative_context_returns_all(self):
        lines = ["+a", "b", "c", "d", "-e"]
        result = _fold_unchanged(lines, context=-1)
        self.assertEqual(result, lines)


if __name__ == "__main__":
    unittest.main()
