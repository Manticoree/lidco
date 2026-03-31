"""Tests for Q137 TextDiffHighlighter."""
from __future__ import annotations
import unittest
from lidco.text.diff_highlighter import TextDiffHighlighter, DiffSegment


class TestDiffSegment(unittest.TestCase):
    def test_dataclass_fields(self):
        s = DiffSegment(text="hi", kind="equal")
        self.assertEqual(s.text, "hi")
        self.assertEqual(s.kind, "equal")

    def test_equality(self):
        a = DiffSegment("x", "insert")
        b = DiffSegment("x", "insert")
        self.assertEqual(a, b)


class TestHighlight(unittest.TestCase):
    def setUp(self):
        self.hl = TextDiffHighlighter()

    def test_identical_strings(self):
        segs = self.hl.highlight("hello", "hello")
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0].kind, "equal")
        self.assertEqual(segs[0].text, "hello")

    def test_completely_different(self):
        segs = self.hl.highlight("abc", "xyz")
        kinds = [s.kind for s in segs]
        self.assertTrue(any(k in ("delete", "insert") for k in kinds))

    def test_insertion_at_end(self):
        segs = self.hl.highlight("abc", "abcd")
        texts = "".join(s.text for s in segs if s.kind in ("equal", "insert"))
        self.assertIn("d", texts)

    def test_deletion(self):
        segs = self.hl.highlight("abcd", "abc")
        deleted = [s for s in segs if s.kind == "delete"]
        self.assertTrue(len(deleted) > 0)

    def test_empty_old(self):
        segs = self.hl.highlight("", "new")
        self.assertTrue(any(s.kind == "insert" for s in segs))

    def test_empty_new(self):
        segs = self.hl.highlight("old", "")
        self.assertTrue(any(s.kind == "delete" for s in segs))

    def test_both_empty(self):
        segs = self.hl.highlight("", "")
        self.assertEqual(segs, [])


class TestWordDiff(unittest.TestCase):
    def setUp(self):
        self.hl = TextDiffHighlighter()

    def test_identical_words(self):
        segs = self.hl.word_diff("hello world", "hello world")
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0].kind, "equal")

    def test_word_insert(self):
        segs = self.hl.word_diff("hello world", "hello big world")
        kinds = [s.kind for s in segs]
        self.assertTrue("insert" in kinds or "delete" in kinds)

    def test_word_delete(self):
        segs = self.hl.word_diff("hello big world", "hello world")
        deleted = [s for s in segs if s.kind == "delete"]
        self.assertTrue(len(deleted) > 0)

    def test_word_replace(self):
        segs = self.hl.word_diff("I like cats", "I like dogs")
        has_change = any(s.kind in ("delete", "insert") for s in segs)
        self.assertTrue(has_change)


class TestFormatInline(unittest.TestCase):
    def setUp(self):
        self.hl = TextDiffHighlighter()

    def test_equal_only(self):
        segs = [DiffSegment("hello", "equal")]
        self.assertEqual(self.hl.format_inline(segs), "hello")

    def test_delete_format(self):
        segs = [DiffSegment("old", "delete")]
        self.assertEqual(self.hl.format_inline(segs), "[-old-]")

    def test_insert_format(self):
        segs = [DiffSegment("new", "insert")]
        self.assertEqual(self.hl.format_inline(segs), "{+new+}")

    def test_mixed(self):
        segs = [
            DiffSegment("keep", "equal"),
            DiffSegment("old", "delete"),
            DiffSegment("new", "insert"),
        ]
        result = self.hl.format_inline(segs)
        self.assertIn("keep", result)
        self.assertIn("[-old-]", result)
        self.assertIn("{+new+}", result)

    def test_empty_segments(self):
        self.assertEqual(self.hl.format_inline([]), "")


class TestStats(unittest.TestCase):
    def setUp(self):
        self.hl = TextDiffHighlighter()

    def test_all_equal(self):
        segs = [DiffSegment("a", "equal"), DiffSegment("b", "equal")]
        st = self.hl.stats(segs)
        self.assertEqual(st["unchanged"], 2)
        self.assertEqual(st["inserts"], 0)

    def test_counts(self):
        segs = [
            DiffSegment("a", "equal"),
            DiffSegment("b", "insert"),
            DiffSegment("c", "delete"),
            DiffSegment("d", "replace"),
        ]
        st = self.hl.stats(segs)
        self.assertEqual(st["unchanged"], 1)
        self.assertEqual(st["inserts"], 1)
        self.assertEqual(st["deletes"], 1)
        self.assertEqual(st["replaces"], 1)

    def test_empty(self):
        st = self.hl.stats([])
        self.assertEqual(st["unchanged"], 0)


if __name__ == "__main__":
    unittest.main()
