"""Tests for BeforeAfterPreview — hunk preview and selective application."""
from __future__ import annotations

import unittest

from lidco.ui.before_after import BeforeAfterPreview, Hunk, PreviewResult


class TestBeforeAfterPreviewBasic(unittest.TestCase):
    def setUp(self):
        self.preview = BeforeAfterPreview()

    def test_identical_texts_no_hunks(self):
        result = self.preview.preview("hello", "hello")
        self.assertEqual(result.hunk_count, 0)
        self.assertFalse(result.has_changes)

    def test_empty_both(self):
        result = self.preview.preview("", "")
        self.assertEqual(result.hunk_count, 0)

    def test_single_addition(self):
        result = self.preview.preview("a\nb", "a\nb\nc")
        self.assertGreater(result.hunk_count, 0)
        self.assertTrue(result.has_changes)

    def test_single_removal(self):
        result = self.preview.preview("a\nb\nc", "a\nc")
        self.assertGreater(result.hunk_count, 0)

    def test_modification(self):
        result = self.preview.preview("a\nb\nc", "a\nB\nc")
        self.assertEqual(result.hunk_count, 1)

    def test_hunk_fields(self):
        result = self.preview.preview("a\nb", "a\nc")
        hunk = result.hunks[0]
        self.assertIsInstance(hunk.old_start, int)
        self.assertIsInstance(hunk.new_start, int)
        self.assertIsInstance(hunk.old_lines, list)
        self.assertIsInstance(hunk.new_lines, list)
        self.assertIsInstance(hunk.content, str)

    def test_hunk_content_has_markers(self):
        result = self.preview.preview("old", "new")
        hunk = result.hunks[0]
        self.assertIn("-", hunk.content)
        self.assertIn("+", hunk.content)

    def test_old_count_new_count(self):
        result = self.preview.preview("a\nb", "a\nc\nd")
        hunk = result.hunks[0]
        self.assertEqual(hunk.old_count, len(hunk.old_lines))
        self.assertEqual(hunk.new_count, len(hunk.new_lines))

    def test_preserves_old_text(self):
        result = self.preview.preview("old text", "new text")
        self.assertEqual(result.old_text, "old text")

    def test_preserves_new_text(self):
        result = self.preview.preview("old text", "new text")
        self.assertEqual(result.new_text, "new text")


class TestAcceptHunks(unittest.TestCase):
    def setUp(self):
        self.ba = BeforeAfterPreview()

    def test_accept_all(self):
        old = "a\nb\nc"
        new = "a\nB\nC"
        pr = self.ba.preview(old, new)
        result = self.ba.accept_all(pr)
        self.assertEqual(result, new)

    def test_reject_all(self):
        old = "a\nb\nc"
        new = "a\nB\nC"
        pr = self.ba.preview(old, new)
        result = self.ba.reject_all(pr)
        self.assertEqual(result, old)

    def test_accept_empty_selection(self):
        old = "a\nb"
        new = "a\nc"
        pr = self.ba.preview(old, new)
        result = self.ba.accept_hunks(pr, [])
        self.assertEqual(result, old)

    def test_accept_no_hunks(self):
        old = "same"
        new = "same"
        pr = self.ba.preview(old, new)
        result = self.ba.accept_hunks(pr, [])
        self.assertEqual(result, old)

    def test_accept_subset_first_hunk(self):
        old = "a\nb\nc\nd\ne"
        new = "a\nB\nc\nd\nE"
        pr = self.ba.preview(old, new)
        # Accept only the first hunk
        result = self.ba.accept_hunks(pr, [0])
        lines = result.split("\n")
        self.assertEqual(lines[0], "a")
        self.assertEqual(lines[1], "B")  # accepted
        self.assertEqual(lines[4], "e")  # not accepted, kept old

    def test_accept_subset_second_hunk(self):
        old = "a\nb\nc\nd\ne"
        new = "a\nB\nc\nd\nE"
        pr = self.ba.preview(old, new)
        # Accept only the second hunk
        result = self.ba.accept_hunks(pr, [1])
        lines = result.split("\n")
        self.assertEqual(lines[1], "b")  # not accepted, kept old
        self.assertEqual(lines[4], "E")  # accepted

    def test_accept_all_via_indices(self):
        old = "a\nb\nc"
        new = "x\ny\nz"
        pr = self.ba.preview(old, new)
        indices = list(range(len(pr.hunks)))
        result = self.ba.accept_hunks(pr, indices)
        self.assertEqual(result, new)

    def test_reject_all_returns_old(self):
        old = "hello\nworld"
        new = "hello\npython"
        pr = self.ba.preview(old, new)
        result = self.ba.reject_all(pr)
        self.assertEqual(result, old)

    def test_accept_all_no_hunks_returns_old(self):
        pr = PreviewResult(hunks=[], old_text="keep", new_text="keep")
        result = self.ba.accept_all(pr)
        self.assertEqual(result, "keep")


class TestPreviewResult(unittest.TestCase):
    def test_hunk_count(self):
        pr = PreviewResult(hunks=[
            Hunk(1, ["a"], 1, ["b"], "- a\n+ b"),
            Hunk(3, ["c"], 3, ["d"], "- c\n+ d"),
        ])
        self.assertEqual(pr.hunk_count, 2)

    def test_has_changes_true(self):
        pr = PreviewResult(hunks=[Hunk(1, ["a"], 1, ["b"], "content")])
        self.assertTrue(pr.has_changes)

    def test_has_changes_false(self):
        pr = PreviewResult()
        self.assertFalse(pr.has_changes)


class TestHunk(unittest.TestCase):
    def test_old_count(self):
        h = Hunk(1, ["a", "b"], 1, ["c"], "content")
        self.assertEqual(h.old_count, 2)

    def test_new_count(self):
        h = Hunk(1, ["a"], 1, ["c", "d", "e"], "content")
        self.assertEqual(h.new_count, 3)


if __name__ == "__main__":
    unittest.main()
