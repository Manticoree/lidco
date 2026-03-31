"""Tests for ThreeWayMerge."""
from __future__ import annotations

import unittest

from lidco.merge.three_way import MergeConflict, MergeResult, ThreeWayMerge


class TestMergeConflict(unittest.TestCase):
    def test_dataclass_fields(self):
        c = MergeConflict(start_line=5, base_text="b", ours_text="o", theirs_text="t")
        self.assertEqual(c.start_line, 5)
        self.assertEqual(c.base_text, "b")
        self.assertEqual(c.ours_text, "o")
        self.assertEqual(c.theirs_text, "t")


class TestMergeResult(unittest.TestCase):
    def test_defaults(self):
        r = MergeResult(merged="hello")
        self.assertEqual(r.merged, "hello")
        self.assertEqual(r.conflicts, [])
        self.assertFalse(r.has_conflicts)
        self.assertEqual(r.auto_resolved, 0)


class TestThreeWayMerge(unittest.TestCase):
    def setUp(self):
        self.m = ThreeWayMerge()

    def test_identical_all_three(self):
        text = "line1\nline2\n"
        result = self.m.merge(text, text, text)
        self.assertFalse(result.has_conflicts)
        self.assertEqual(result.merged, text)

    def test_ours_only_change(self):
        base = "line1\nline2\n"
        ours = "line1\nmodified\n"
        theirs = "line1\nline2\n"
        result = self.m.merge(base, ours, theirs)
        self.assertFalse(result.has_conflicts)
        self.assertIn("modified", result.merged)

    def test_theirs_only_change(self):
        base = "line1\nline2\n"
        ours = "line1\nline2\n"
        theirs = "line1\nchanged\n"
        result = self.m.merge(base, ours, theirs)
        self.assertFalse(result.has_conflicts)
        self.assertIn("changed", result.merged)

    def test_both_same_change(self):
        base = "line1\nline2\n"
        ours = "line1\nsame\n"
        theirs = "line1\nsame\n"
        result = self.m.merge(base, ours, theirs)
        self.assertFalse(result.has_conflicts)
        self.assertIn("same", result.merged)
        self.assertGreater(result.auto_resolved, 0)

    def test_conflict_detected(self):
        base = "line1\nline2\n"
        ours = "line1\nours_change\n"
        theirs = "line1\ntheirs_change\n"
        result = self.m.merge(base, ours, theirs)
        self.assertTrue(result.has_conflicts)
        self.assertEqual(len(result.conflicts), 1)

    def test_conflict_texts(self):
        base = "a\nb\n"
        ours = "a\nours\n"
        theirs = "a\ntheirs\n"
        result = self.m.merge(base, ours, theirs)
        c = result.conflicts[0]
        self.assertIn("ours", c.ours_text)
        self.assertIn("theirs", c.theirs_text)

    def test_conflict_markers_in_merged(self):
        base = "a\nb\n"
        ours = "a\nX\n"
        theirs = "a\nY\n"
        result = self.m.merge(base, ours, theirs)
        self.assertIn("<<<<<<< ours", result.merged)
        self.assertIn("=======", result.merged)
        self.assertIn(">>>>>>> theirs", result.merged)

    def test_can_auto_merge_true(self):
        base = "a\nb\n"
        ours = "a\nb\nc\n"
        theirs = "a\nb\n"
        self.assertTrue(self.m.can_auto_merge(base, ours, theirs))

    def test_can_auto_merge_false(self):
        base = "a\nb\n"
        ours = "a\nX\n"
        theirs = "a\nY\n"
        self.assertFalse(self.m.can_auto_merge(base, ours, theirs))

    def test_format_conflicts_empty(self):
        result = MergeResult(merged="x")
        self.assertEqual(self.m.format_conflicts(result), "")

    def test_format_conflicts_output(self):
        c = MergeConflict(start_line=3, base_text="b", ours_text="o", theirs_text="t")
        result = MergeResult(merged="x", conflicts=[c], has_conflicts=True)
        out = self.m.format_conflicts(result)
        self.assertIn("<<<<<<< ours", out)
        self.assertIn("=======", out)
        self.assertIn(">>>>>>> theirs", out)
        self.assertIn("Conflict 1", out)

    def test_empty_inputs(self):
        result = self.m.merge("", "", "")
        self.assertFalse(result.has_conflicts)
        self.assertEqual(result.merged, "")

    def test_addition_ours(self):
        base = "a\n"
        ours = "a\nnew_line\n"
        theirs = "a\n"
        result = self.m.merge(base, ours, theirs)
        self.assertFalse(result.has_conflicts)
        self.assertIn("new_line", result.merged)

    def test_deletion_theirs(self):
        base = "a\nb\nc\n"
        ours = "a\nb\nc\n"
        theirs = "a\nc\n"
        result = self.m.merge(base, ours, theirs)
        self.assertFalse(result.has_conflicts)
        self.assertNotIn("b\n", result.merged.split("a\n")[-1].split("c\n")[0] if "c" in result.merged else result.merged)

    def test_multiple_conflicts(self):
        base = "a\nb\nc\nd\n"
        ours = "X\nb\nY\nd\n"
        theirs = "Z\nb\nW\nd\n"
        result = self.m.merge(base, ours, theirs)
        self.assertTrue(result.has_conflicts)
        self.assertGreaterEqual(len(result.conflicts), 1)

    def test_auto_resolved_count(self):
        base = "a\nb\n"
        ours = "a\nchanged\n"
        theirs = "a\nb\n"
        result = self.m.merge(base, ours, theirs)
        self.assertGreater(result.auto_resolved, 0)

    def test_merge_result_has_conflicts_flag(self):
        result = MergeResult(merged="x", conflicts=[], has_conflicts=False)
        self.assertFalse(result.has_conflicts)

    def test_format_conflicts_numbering(self):
        c1 = MergeConflict(start_line=1, base_text="", ours_text="A", theirs_text="B")
        c2 = MergeConflict(start_line=5, base_text="", ours_text="C", theirs_text="D")
        result = MergeResult(merged="", conflicts=[c1, c2], has_conflicts=True)
        out = self.m.format_conflicts(result)
        self.assertIn("Conflict 1", out)
        self.assertIn("Conflict 2", out)

    def test_single_line_conflict(self):
        base = "only\n"
        ours = "ours_only\n"
        theirs = "theirs_only\n"
        result = self.m.merge(base, ours, theirs)
        self.assertTrue(result.has_conflicts)

    def test_no_trailing_newline(self):
        base = "a"
        ours = "b"
        theirs = "a"
        result = self.m.merge(base, ours, theirs)
        self.assertFalse(result.has_conflicts)

    def test_large_file_merge(self):
        base = "\n".join(f"line{i}" for i in range(100)) + "\n"
        ours = base.replace("line50", "ours50")
        theirs = base.replace("line80", "theirs80")
        result = self.m.merge(base, ours, theirs)
        self.assertFalse(result.has_conflicts)
        self.assertIn("ours50", result.merged)
        self.assertIn("theirs80", result.merged)


if __name__ == "__main__":
    unittest.main()
