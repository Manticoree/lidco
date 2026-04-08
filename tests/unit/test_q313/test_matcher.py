"""Tests for snapshot_test.matcher — SnapshotMatcher."""

import tempfile
import unittest

from lidco.snapshot_test.manager import SnapshotManager
from lidco.snapshot_test.matcher import SnapshotMatcher, MatchResult


class TestMatcherBase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.mgr = SnapshotManager(self._td.name)
        self.matcher = SnapshotMatcher(self.mgr)

    def tearDown(self):
        self._td.cleanup()


class TestMatch(TestMatcherBase):
    def test_first_run_creates_snapshot(self):
        result = self.matcher.match("new_snap", "hello")
        self.assertTrue(result.matched)
        self.assertTrue(self.mgr.exists("new_snap"))

    def test_matching_content(self):
        self.mgr.create("snap1", "hello")
        result = self.matcher.match("snap1", "hello")
        self.assertTrue(result.matched)
        self.assertEqual(result.diff, "")

    def test_mismatch_produces_diff(self):
        self.mgr.create("snap1", "hello")
        result = self.matcher.match("snap1", "world")
        self.assertFalse(result.matched)
        self.assertIn("-hello", result.diff)
        self.assertIn("+world", result.diff)

    def test_mismatch_expected_actual(self):
        self.mgr.create("snap1", "old")
        result = self.matcher.match("snap1", "new")
        self.assertEqual(result.expected, "old")
        self.assertEqual(result.actual, "new")

    def test_match_result_snapshot_name(self):
        result = self.matcher.match("s1", "data")
        self.assertEqual(result.snapshot_name, "s1")


class TestUpdateMode(TestMatcherBase):
    def setUp(self):
        super().setUp()
        self.matcher = SnapshotMatcher(self.mgr, update=True)

    def test_update_mode_flag(self):
        self.assertTrue(self.matcher.update_mode)

    def test_mismatch_updates_snapshot(self):
        self.mgr.create("snap1", "old")
        result = self.matcher.match("snap1", "new")
        self.assertTrue(result.matched)
        rec = self.mgr.read("snap1")
        self.assertEqual(rec.content, "new")

    def test_diff_still_generated_on_update(self):
        self.mgr.create("snap1", "old")
        result = self.matcher.match("snap1", "new")
        self.assertNotEqual(result.diff, "")


class TestPartialMatch(TestMatcherBase):
    def test_contains_match(self):
        self.mgr.create("snap1", "hello world foo")
        result = self.matcher.match_partial("snap1", "hello world foo", contains="world")
        self.assertTrue(result.matched)

    def test_contains_mismatch(self):
        self.mgr.create("snap1", "hello world")
        result = self.matcher.match_partial("snap1", "goodbye", contains="world")
        self.assertFalse(result.matched)

    def test_pattern_match(self):
        self.mgr.create("snap1", "line1\nline2\nline3")
        result = self.matcher.match_partial("snap1", "line1\nline2\nline3", pattern="line*")
        self.assertTrue(result.matched)

    def test_pattern_mismatch(self):
        self.mgr.create("snap1", "line1\nline2")
        result = self.matcher.match_partial("snap1", "line1\nline99", pattern="line*")
        self.assertFalse(result.matched)

    def test_first_run_creates(self):
        result = self.matcher.match_partial("new_snap", "data", contains="da")
        self.assertTrue(result.matched)
        self.assertTrue(self.mgr.exists("new_snap"))

    def test_partial_update_mode_contains(self):
        matcher = SnapshotMatcher(self.mgr, update=True)
        self.mgr.create("snap1", "old_content")
        result = matcher.match_partial("snap1", "new_content", contains="old")
        self.assertTrue(result.matched)

    def test_partial_update_mode_pattern(self):
        matcher = SnapshotMatcher(self.mgr, update=True)
        self.mgr.create("snap1", "aaa\nbbb")
        result = matcher.match_partial("snap1", "aaa\nccc", pattern="*")
        self.assertTrue(result.matched)

    def test_fallback_to_full_match(self):
        self.mgr.create("snap1", "same")
        result = self.matcher.match_partial("snap1", "same")
        self.assertTrue(result.matched)


class TestDiff(TestMatcherBase):
    def test_diff_identical(self):
        self.mgr.create("snap1", "same")
        d = self.matcher.diff("snap1", "same")
        self.assertEqual(d, "")

    def test_diff_different(self):
        self.mgr.create("snap1", "old")
        d = self.matcher.diff("snap1", "new")
        self.assertIn("-old", d)
        self.assertIn("+new", d)

    def test_diff_nonexistent(self):
        d = self.matcher.diff("nope", "val")
        self.assertEqual(d, "")


if __name__ == "__main__":
    unittest.main()
