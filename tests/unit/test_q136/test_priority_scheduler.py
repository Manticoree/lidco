"""Tests for PriorityScheduler."""
from __future__ import annotations

import unittest
from lidco.scheduling.priority_scheduler import PriorityScheduler, ScheduledTask


class TestScheduledTask(unittest.TestCase):
    def test_dataclass_fields(self):
        t = ScheduledTask(id="a", name="t", priority=1, category="c", created_at=0.0)
        self.assertEqual(t.id, "a")
        self.assertEqual(t.priority, 1)
        self.assertIsNone(t.payload)

    def test_lt_by_priority(self):
        a = ScheduledTask(id="a", name="a", priority=1, category="c", created_at=0.0)
        b = ScheduledTask(id="b", name="b", priority=2, category="c", created_at=0.0)
        self.assertTrue(a < b)

    def test_lt_same_priority_by_time(self):
        a = ScheduledTask(id="a", name="a", priority=1, category="c", created_at=1.0)
        b = ScheduledTask(id="b", name="b", priority=1, category="c", created_at=2.0)
        self.assertTrue(a < b)


class TestPriorityScheduler(unittest.TestCase):
    def setUp(self):
        self.ps = PriorityScheduler()

    def test_schedule_returns_task(self):
        t = self.ps.schedule("job1", priority=5, category="build")
        self.assertIsInstance(t, ScheduledTask)
        self.assertEqual(t.name, "job1")
        self.assertEqual(t.priority, 5)
        self.assertEqual(t.category, "build")

    def test_schedule_generates_unique_ids(self):
        t1 = self.ps.schedule("a")
        t2 = self.ps.schedule("b")
        self.assertNotEqual(t1.id, t2.id)

    def test_schedule_default_category(self):
        t = self.ps.schedule("x")
        self.assertEqual(t.category, "default")

    def test_schedule_with_payload(self):
        t = self.ps.schedule("x", payload={"key": "val"})
        self.assertEqual(t.payload, {"key": "val"})

    def test_next_returns_highest_priority(self):
        self.ps.schedule("low", priority=10)
        self.ps.schedule("high", priority=1)
        self.ps.schedule("mid", priority=5)
        t = self.ps.next()
        self.assertIsNotNone(t)
        self.assertEqual(t.name, "high")

    def test_next_empty_returns_none(self):
        self.assertIsNone(self.ps.next())

    def test_next_removes_task(self):
        self.ps.schedule("a", priority=1)
        self.ps.next()
        self.assertTrue(self.ps.is_empty)

    def test_peek_returns_without_removing(self):
        self.ps.schedule("a", priority=1)
        t = self.ps.peek()
        self.assertIsNotNone(t)
        self.assertEqual(self.ps.size, 1)

    def test_peek_empty_returns_none(self):
        self.assertIsNone(self.ps.peek())

    def test_cancel_existing_task(self):
        t = self.ps.schedule("a", priority=1)
        self.assertTrue(self.ps.cancel(t.id))
        self.assertEqual(self.ps.size, 0)

    def test_cancel_nonexistent_returns_false(self):
        self.assertFalse(self.ps.cancel("nope"))

    def test_cancelled_task_skipped_by_next(self):
        t1 = self.ps.schedule("cancel_me", priority=1)
        self.ps.schedule("keep_me", priority=2)
        self.ps.cancel(t1.id)
        t = self.ps.next()
        self.assertIsNotNone(t)
        self.assertEqual(t.name, "keep_me")

    def test_cancelled_task_skipped_by_peek(self):
        t1 = self.ps.schedule("cancel_me", priority=1)
        self.ps.schedule("keep_me", priority=2)
        self.ps.cancel(t1.id)
        t = self.ps.peek()
        self.assertEqual(t.name, "keep_me")

    def test_list_by_category(self):
        self.ps.schedule("a", priority=2, category="build")
        self.ps.schedule("b", priority=1, category="build")
        self.ps.schedule("c", priority=1, category="test")
        result = self.ps.list_by_category("build")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].name, "b")

    def test_list_by_category_empty(self):
        self.assertEqual(self.ps.list_by_category("none"), [])

    def test_size_property(self):
        self.assertEqual(self.ps.size, 0)
        self.ps.schedule("a")
        self.assertEqual(self.ps.size, 1)

    def test_is_empty_property(self):
        self.assertTrue(self.ps.is_empty)
        self.ps.schedule("a")
        self.assertFalse(self.ps.is_empty)

    def test_multiple_next_drains_queue(self):
        for i in range(5):
            self.ps.schedule(f"t{i}", priority=i)
        names = []
        while not self.ps.is_empty:
            t = self.ps.next()
            names.append(t.name)
        self.assertEqual(names, ["t0", "t1", "t2", "t3", "t4"])

    def test_cancel_then_next_returns_none_when_all_cancelled(self):
        t = self.ps.schedule("only")
        self.ps.cancel(t.id)
        self.assertIsNone(self.ps.next())


if __name__ == "__main__":
    unittest.main()
