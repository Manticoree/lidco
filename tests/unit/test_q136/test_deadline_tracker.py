"""Tests for DeadlineTracker."""
from __future__ import annotations

import time
import unittest
from lidco.scheduling.deadline_tracker import Deadline, DeadlineTracker


class TestDeadline(unittest.TestCase):
    def test_defaults(self):
        d = Deadline(task_id="a", name="task a", due_at=100.0)
        self.assertFalse(d.completed)
        self.assertIsNone(d.completed_at)

    def test_fields(self):
        d = Deadline(task_id="a", name="n", due_at=50.0, completed=True, completed_at=60.0)
        self.assertTrue(d.completed)
        self.assertEqual(d.completed_at, 60.0)


class TestDeadlineTracker(unittest.TestCase):
    def setUp(self):
        self.dt = DeadlineTracker()

    def test_add_returns_deadline(self):
        dl = self.dt.add("t1", "Task 1", 9999999999.0)
        self.assertIsInstance(dl, Deadline)
        self.assertEqual(dl.task_id, "t1")

    def test_complete_existing(self):
        self.dt.add("t1", "Task 1", 9999999999.0)
        self.assertTrue(self.dt.complete("t1"))

    def test_complete_nonexistent(self):
        self.assertFalse(self.dt.complete("nope"))

    def test_complete_sets_completed_at(self):
        self.dt.add("t1", "Task 1", 9999999999.0)
        self.dt.complete("t1")
        # verify via summary that completed count increased
        s = self.dt.summary()
        self.assertEqual(s["completed"], 1)

    def test_overdue_returns_past_due(self):
        now = time.time()
        self.dt.add("t1", "old", now - 100)
        overdue = self.dt.overdue(now=now)
        self.assertEqual(len(overdue), 1)
        self.assertEqual(overdue[0].task_id, "t1")

    def test_overdue_excludes_completed(self):
        now = time.time()
        self.dt.add("t1", "old", now - 100)
        self.dt.complete("t1")
        overdue = self.dt.overdue(now=now)
        self.assertEqual(len(overdue), 0)

    def test_overdue_excludes_future(self):
        now = time.time()
        self.dt.add("t1", "future", now + 1000)
        overdue = self.dt.overdue(now=now)
        self.assertEqual(len(overdue), 0)

    def test_overdue_sorted_by_due_at(self):
        now = time.time()
        self.dt.add("t2", "later", now - 50)
        self.dt.add("t1", "earlier", now - 100)
        overdue = self.dt.overdue(now=now)
        self.assertEqual(overdue[0].task_id, "t1")

    def test_upcoming_within_window(self):
        now = time.time()
        self.dt.add("t1", "soon", now + 1800)  # 30 min
        upcoming = self.dt.upcoming(seconds=3600, now=now)
        self.assertEqual(len(upcoming), 1)

    def test_upcoming_excludes_past(self):
        now = time.time()
        self.dt.add("t1", "past", now - 100)
        upcoming = self.dt.upcoming(seconds=3600, now=now)
        self.assertEqual(len(upcoming), 0)

    def test_upcoming_excludes_far_future(self):
        now = time.time()
        self.dt.add("t1", "far", now + 99999)
        upcoming = self.dt.upcoming(seconds=3600, now=now)
        self.assertEqual(len(upcoming), 0)

    def test_upcoming_excludes_completed(self):
        now = time.time()
        self.dt.add("t1", "soon", now + 100)
        self.dt.complete("t1")
        upcoming = self.dt.upcoming(seconds=3600, now=now)
        self.assertEqual(len(upcoming), 0)

    def test_upcoming_custom_window(self):
        now = time.time()
        self.dt.add("t1", "in 10s", now + 10)
        self.assertEqual(len(self.dt.upcoming(seconds=5, now=now)), 0)
        self.assertEqual(len(self.dt.upcoming(seconds=20, now=now)), 1)

    def test_summary_empty(self):
        s = self.dt.summary()
        self.assertEqual(s, {"total": 0, "completed": 0, "overdue": 0, "upcoming": 0})

    def test_summary_counts(self):
        now = time.time()
        self.dt.add("past", "past", now - 100)
        self.dt.add("soon", "soon", now + 1800)
        self.dt.add("done", "done", now + 500)
        self.dt.complete("done")
        s = self.dt.summary(now=now)
        self.assertEqual(s["total"], 3)
        self.assertEqual(s["completed"], 1)
        self.assertEqual(s["overdue"], 1)
        self.assertEqual(s["upcoming"], 1)

    def test_add_overwrites_same_id(self):
        self.dt.add("t1", "first", 100.0)
        self.dt.add("t1", "second", 200.0)
        s = self.dt.summary(now=300.0)
        self.assertEqual(s["total"], 1)

    def test_overdue_empty(self):
        self.assertEqual(self.dt.overdue(), [])

    def test_upcoming_empty(self):
        self.assertEqual(self.dt.upcoming(), [])


if __name__ == "__main__":
    unittest.main()
