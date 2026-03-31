"""Tests for ActionTracker."""
from __future__ import annotations

import unittest

from lidco.flow.action_tracker import ActionTracker, TrackedAction


class TestTrackedAction(unittest.TestCase):
    def test_dataclass_fields(self):
        a = TrackedAction(action_type="edit", detail="changed file", timestamp=1.0)
        self.assertEqual(a.action_type, "edit")
        self.assertEqual(a.detail, "changed file")
        self.assertEqual(a.timestamp, 1.0)
        self.assertIsNone(a.file_path)
        self.assertTrue(a.success)

    def test_with_file_path_and_failure(self):
        a = TrackedAction(
            action_type="error", detail="crash", timestamp=2.0,
            file_path="/a/b.py", success=False,
        )
        self.assertEqual(a.file_path, "/a/b.py")
        self.assertFalse(a.success)


class TestTrack(unittest.TestCase):
    def setUp(self):
        self.t = ActionTracker()

    def test_track_adds_action(self):
        self.t.track("edit", "modified file")
        self.assertEqual(len(self.t.recent()), 1)

    def test_track_with_file_path(self):
        self.t.track("read", "opened", file_path="/x.py")
        self.assertEqual(self.t.recent()[0].file_path, "/x.py")

    def test_track_failure(self):
        self.t.track("error", "boom", success=False)
        self.assertFalse(self.t.recent()[0].success)

    def test_max_history_enforced(self):
        tracker = ActionTracker(max_history=5)
        for i in range(10):
            tracker.track("edit", f"op{i}")
        self.assertEqual(len(tracker.recent(limit=100)), 5)


class TestRecent(unittest.TestCase):
    def setUp(self):
        self.t = ActionTracker()
        for i in range(30):
            self.t.track("edit", f"op{i}")

    def test_recent_default_limit(self):
        r = self.t.recent()
        self.assertEqual(len(r), 20)

    def test_recent_custom_limit(self):
        r = self.t.recent(limit=5)
        self.assertEqual(len(r), 5)
        self.assertEqual(r[-1].detail, "op29")

    def test_recent_limit_larger_than_history(self):
        r = self.t.recent(limit=100)
        self.assertEqual(len(r), 30)


class TestByType(unittest.TestCase):
    def test_by_type_filters(self):
        t = ActionTracker()
        t.track("edit", "e1")
        t.track("read", "r1")
        t.track("edit", "e2")
        self.assertEqual(len(t.by_type("edit")), 2)
        self.assertEqual(len(t.by_type("read")), 1)
        self.assertEqual(len(t.by_type("search")), 0)


class TestByFile(unittest.TestCase):
    def test_by_file_filters(self):
        t = ActionTracker()
        t.track("edit", "e1", file_path="/a.py")
        t.track("edit", "e2", file_path="/b.py")
        t.track("read", "r1", file_path="/a.py")
        self.assertEqual(len(t.by_file("/a.py")), 2)
        self.assertEqual(len(t.by_file("/b.py")), 1)
        self.assertEqual(len(t.by_file("/c.py")), 0)


class TestErrorRate(unittest.TestCase):
    def test_error_rate_no_actions(self):
        t = ActionTracker()
        self.assertAlmostEqual(t.error_rate(), 0.0)

    def test_error_rate_all_success(self):
        t = ActionTracker()
        for _ in range(10):
            t.track("edit", "ok")
        self.assertAlmostEqual(t.error_rate(), 0.0)

    def test_error_rate_all_fail(self):
        t = ActionTracker()
        for _ in range(10):
            t.track("error", "fail", success=False)
        self.assertAlmostEqual(t.error_rate(), 1.0)

    def test_error_rate_mixed(self):
        t = ActionTracker()
        for _ in range(8):
            t.track("edit", "ok")
        for _ in range(2):
            t.track("error", "fail", success=False)
        self.assertAlmostEqual(t.error_rate(window=10), 0.2)


class TestMostActiveFiles(unittest.TestCase):
    def test_most_active_files(self):
        t = ActionTracker()
        for _ in range(5):
            t.track("edit", "e", file_path="/a.py")
        for _ in range(3):
            t.track("edit", "e", file_path="/b.py")
        t.track("edit", "e", file_path="/c.py")
        result = t.most_active_files(limit=2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], ("/a.py", 5))
        self.assertEqual(result[1], ("/b.py", 3))

    def test_most_active_files_excludes_none(self):
        t = ActionTracker()
        t.track("command", "help")
        t.track("edit", "e", file_path="/a.py")
        result = t.most_active_files()
        self.assertEqual(len(result), 1)

    def test_most_active_files_empty(self):
        t = ActionTracker()
        self.assertEqual(t.most_active_files(), [])


class TestClearAndStats(unittest.TestCase):
    def test_clear(self):
        t = ActionTracker()
        t.track("edit", "e")
        t.clear()
        self.assertEqual(len(t.recent()), 0)

    def test_stats_empty(self):
        t = ActionTracker()
        self.assertEqual(t.stats(), {})

    def test_stats_counts(self):
        t = ActionTracker()
        t.track("edit", "e1")
        t.track("edit", "e2")
        t.track("read", "r1")
        s = t.stats()
        self.assertEqual(s["edit"], 2)
        self.assertEqual(s["read"], 1)


if __name__ == "__main__":
    unittest.main()
