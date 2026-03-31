"""Tests for RecentFiles (Q145 Task 859)."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from lidco.ux.recent_files import RecentFiles, RecentFile


class TestRecentFile(unittest.TestCase):
    def test_dataclass_fields(self):
        f = RecentFile(path="/a/b.py", last_accessed=1.0, access_count=3, action="edit")
        self.assertEqual(f.path, "/a/b.py")
        self.assertEqual(f.last_accessed, 1.0)
        self.assertEqual(f.access_count, 3)
        self.assertEqual(f.action, "edit")


class TestRecentFiles(unittest.TestCase):
    def setUp(self):
        self.rf = RecentFiles(max_files=5)

    def test_initial_size_zero(self):
        self.assertEqual(self.rf.size, 0)

    def test_track_adds_file(self):
        self.rf.track("/a.py")
        self.assertEqual(self.rf.size, 1)

    def test_track_increments_count(self):
        self.rf.track("/a.py")
        self.rf.track("/a.py")
        files = self.rf.recent(1)
        self.assertEqual(files[0].access_count, 2)

    def test_track_updates_action(self):
        self.rf.track("/a.py", "read")
        self.rf.track("/a.py", "write")
        files = self.rf.recent(1)
        self.assertEqual(files[0].action, "write")

    def test_max_files_eviction(self):
        for i in range(10):
            self.rf.track(f"/file{i}.py")
        self.assertEqual(self.rf.size, 5)

    def test_recent_returns_newest_first(self):
        self.rf.track("/old.py")
        self.rf.track("/new.py")
        result = self.rf.recent(2)
        self.assertEqual(result[0].path, "/new.py")

    def test_recent_limits_n(self):
        for i in range(5):
            self.rf.track(f"/f{i}.py")
        result = self.rf.recent(2)
        self.assertEqual(len(result), 2)

    def test_frequent_returns_most_accessed(self):
        self.rf.track("/a.py")
        self.rf.track("/b.py")
        self.rf.track("/a.py")
        self.rf.track("/a.py")
        result = self.rf.frequent(1)
        self.assertEqual(result[0].path, "/a.py")
        self.assertEqual(result[0].access_count, 3)

    def test_by_action_read(self):
        self.rf.track("/a.py", "read")
        self.rf.track("/b.py", "write")
        self.rf.track("/c.py", "read")
        result = self.rf.by_action("read")
        self.assertEqual(len(result), 2)

    def test_by_action_no_match(self):
        self.rf.track("/a.py", "read")
        self.assertEqual(self.rf.by_action("edit"), [])

    def test_search_substring(self):
        self.rf.track("/src/main.py")
        self.rf.track("/src/util.py")
        self.rf.track("/tests/test.py")
        result = self.rf.search("src")
        self.assertEqual(len(result), 2)

    def test_search_case_insensitive(self):
        self.rf.track("/SRC/Main.py")
        result = self.rf.search("src")
        self.assertEqual(len(result), 1)

    def test_search_no_match(self):
        self.rf.track("/a.py")
        self.assertEqual(self.rf.search("zzz"), [])

    def test_clear(self):
        self.rf.track("/a.py")
        self.rf.clear()
        self.assertEqual(self.rf.size, 0)

    def test_default_max_files(self):
        rf = RecentFiles()
        self.assertEqual(rf._max_files, 50)

    def test_track_sets_timestamp(self):
        before = time.time()
        self.rf.track("/a.py")
        after = time.time()
        f = self.rf.recent(1)[0]
        self.assertGreaterEqual(f.last_accessed, before)
        self.assertLessEqual(f.last_accessed, after)

    def test_frequent_empty(self):
        self.assertEqual(self.rf.frequent(), [])

    def test_recent_empty(self):
        self.assertEqual(self.rf.recent(), [])

    def test_by_action_write(self):
        self.rf.track("/a.py", "write")
        self.rf.track("/b.py", "edit")
        result = self.rf.by_action("write")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].path, "/a.py")


if __name__ == "__main__":
    unittest.main()
