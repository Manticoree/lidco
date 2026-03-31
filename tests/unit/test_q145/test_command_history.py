"""Tests for CommandHistory (Q145 Task 857)."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from lidco.ux.command_history import CommandHistory, HistoryEntry


class TestHistoryEntry(unittest.TestCase):
    def test_dataclass_fields(self):
        e = HistoryEntry(command="/help", timestamp=1.0, success=True, duration=0.5)
        self.assertEqual(e.command, "/help")
        self.assertEqual(e.timestamp, 1.0)
        self.assertTrue(e.success)
        self.assertEqual(e.duration, 0.5)

    def test_duration_defaults_none(self):
        e = HistoryEntry(command="x", timestamp=0.0, success=False)
        self.assertIsNone(e.duration)


class TestCommandHistory(unittest.TestCase):
    def setUp(self):
        self.h = CommandHistory(max_entries=5)

    def test_initial_size_zero(self):
        self.assertEqual(self.h.size, 0)

    def test_add_increments_size(self):
        self.h.add("/help")
        self.assertEqual(self.h.size, 1)

    def test_add_records_success(self):
        self.h.add("/build", success=False, duration=1.2)
        entry = self.h.get(0)
        self.assertIsNotNone(entry)
        self.assertFalse(entry.success)
        self.assertEqual(entry.duration, 1.2)

    def test_max_entries_eviction(self):
        for i in range(10):
            self.h.add(f"/cmd{i}")
        self.assertEqual(self.h.size, 5)
        # oldest should be evicted
        self.assertIsNone(self.h.get(5))

    def test_get_zero_is_most_recent(self):
        self.h.add("/first")
        self.h.add("/second")
        self.assertEqual(self.h.get(0).command, "/second")
        self.assertEqual(self.h.get(1).command, "/first")

    def test_get_negative_returns_none(self):
        self.h.add("/x")
        self.assertIsNone(self.h.get(-1))

    def test_get_out_of_range_returns_none(self):
        self.assertIsNone(self.h.get(0))

    def test_last_returns_newest_first(self):
        self.h.add("/a")
        self.h.add("/b")
        self.h.add("/c")
        result = self.h.last(2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].command, "/c")
        self.assertEqual(result[1].command, "/b")

    def test_last_more_than_available(self):
        self.h.add("/only")
        result = self.h.last(10)
        self.assertEqual(len(result), 1)

    def test_search_substring(self):
        self.h.add("/build project")
        self.h.add("/test unit")
        self.h.add("/build all")
        results = self.h.search("build")
        self.assertEqual(len(results), 2)

    def test_search_case_insensitive(self):
        self.h.add("/Build")
        results = self.h.search("build")
        self.assertEqual(len(results), 1)

    def test_search_no_match(self):
        self.h.add("/help")
        self.assertEqual(self.h.search("zzz"), [])

    def test_frequent(self):
        self.h.add("/help")
        self.h.add("/build")
        self.h.add("/help")
        self.h.add("/help")
        freqs = self.h.frequent(2)
        self.assertEqual(freqs[0], ("/help", 3))
        self.assertEqual(freqs[1], ("/build", 1))

    def test_frequent_empty(self):
        self.assertEqual(self.h.frequent(), [])

    def test_clear(self):
        self.h.add("/x")
        self.h.clear()
        self.assertEqual(self.h.size, 0)

    def test_undo_last_returns_most_recent(self):
        self.h.add("/a")
        self.h.add("/b")
        undone = self.h.undo_last()
        self.assertEqual(undone.command, "/b")
        self.assertEqual(self.h.size, 1)

    def test_undo_last_empty_returns_none(self):
        self.assertIsNone(self.h.undo_last())

    def test_default_max_entries(self):
        h = CommandHistory()
        self.assertEqual(h._max_entries, 500)

    def test_add_sets_timestamp(self):
        before = time.time()
        self.h.add("/cmd")
        after = time.time()
        entry = self.h.get(0)
        self.assertGreaterEqual(entry.timestamp, before)
        self.assertLessEqual(entry.timestamp, after)

    def test_frequent_limits_n(self):
        for i in range(20):
            self.h = CommandHistory(max_entries=500)
        for i in range(5):
            h2 = CommandHistory()
            for j in range(i + 1):
                h2.add(f"/cmd{i}")
        result = h2.frequent(2)
        self.assertLessEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
