"""Tests for lidco.githistory.bisect."""
from __future__ import annotations

import unittest

from lidco.githistory.bisect import BisectAssistant, BisectStep


class TestBisectStep(unittest.TestCase):
    def test_fields(self):
        s = BisectStep(hash="abc", passed=True)
        self.assertEqual(s.hash, "abc")
        self.assertTrue(s.passed)

    def test_immutable(self):
        s = BisectStep(hash="abc", passed=False)
        with self.assertRaises(AttributeError):
            s.hash = "new"  # type: ignore[misc]


class TestBisectAssistant(unittest.TestCase):
    def _make_commits(self, n: int = 8) -> list[str]:
        return [f"c{i}" for i in range(n)]

    def test_start_requires_commits(self):
        ba = BisectAssistant()
        with self.assertRaises(ValueError):
            ba.start("c0", "c1", None)

    def test_start_requires_two_commits(self):
        ba = BisectAssistant()
        with self.assertRaises(ValueError):
            ba.start("c0", "c0", ["c0"])

    def test_start_good_must_be_in_list(self):
        ba = BisectAssistant()
        with self.assertRaises(ValueError):
            ba.start("missing", "c1", ["c0", "c1"])

    def test_start_bad_must_be_in_list(self):
        ba = BisectAssistant()
        with self.assertRaises(ValueError):
            ba.start("c0", "missing", ["c0", "c1"])

    def test_start_good_before_bad(self):
        ba = BisectAssistant()
        with self.assertRaises(ValueError):
            ba.start("c1", "c0", ["c0", "c1"])

    def test_current_before_start_raises(self):
        ba = BisectAssistant()
        with self.assertRaises(RuntimeError):
            ba.current()

    def test_basic_bisect(self):
        commits = self._make_commits(8)
        ba = BisectAssistant()
        ba.start("c0", "c7", commits)
        # midpoint of [0, 7] = 3 -> c3
        self.assertEqual(ba.current(), "c3")

    def test_full_bisect_finds_bad(self):
        # Bad commit is c5 (c0-c4 pass, c5-c7 fail)
        commits = self._make_commits(8)
        ba = BisectAssistant()
        ba.start("c0", "c7", commits)

        max_steps = 10
        for _ in range(max_steps):
            cur = ba.current()
            idx = commits.index(cur)
            passed = idx < 5  # c0-c4 good, c5-c7 bad
            result = ba.test_commit(cur, passed)
            if result == "found":
                break

        self.assertEqual(ba.found(), "c5")

    def test_history_recorded(self):
        commits = self._make_commits(8)
        ba = BisectAssistant()
        ba.start("c0", "c7", commits)
        ba.test_commit(ba.current(), True)
        ba.test_commit(ba.current(), False)
        hist = ba.history()
        self.assertEqual(len(hist), 2)
        self.assertIsInstance(hist[0], BisectStep)

    def test_steps_remaining_decreases(self):
        commits = self._make_commits(16)
        ba = BisectAssistant()
        ba.start("c0", "c15", commits)
        initial = ba.steps_remaining()
        ba.test_commit(ba.current(), True)
        after = ba.steps_remaining()
        self.assertLessEqual(after, initial)

    def test_steps_remaining_zero_when_found(self):
        commits = ["c0", "c1"]
        ba = BisectAssistant()
        ba.start("c0", "c1", commits)
        self.assertEqual(ba.steps_remaining(), 0)

    def test_found_returns_none_initially(self):
        ba = BisectAssistant()
        commits = self._make_commits(4)
        ba.start("c0", "c3", commits)
        self.assertIsNone(ba.found())

    def test_test_commit_after_found(self):
        commits = ["c0", "c1"]
        ba = BisectAssistant()
        ba.start("c0", "c1", commits)
        # With only 2 commits, bad_idx - good_idx = 1, so it should find immediately
        # Actually steps_remaining is 0 but we need to test once
        # The midpoint is 0, test it
        result = ba.test_commit("c0", True)
        self.assertEqual(result, "found")
        # After found, test_commit returns "found" again
        result2 = ba.test_commit("c1", False)
        self.assertEqual(result2, "found")


if __name__ == "__main__":
    unittest.main()
