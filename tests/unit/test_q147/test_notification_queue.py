"""Tests for NotificationQueue (Task 867)."""
from __future__ import annotations

import time
import unittest

from lidco.alerts.notification_queue import Notification, NotificationQueue


class TestNotification(unittest.TestCase):
    def test_dataclass_fields(self):
        n = Notification(id="abc", level="info", title="T", message="M", timestamp=1.0)
        self.assertEqual(n.id, "abc")
        self.assertEqual(n.level, "info")
        self.assertFalse(n.read)
        self.assertEqual(n.source, "system")

    def test_custom_source(self):
        n = Notification(id="x", level="error", title="T", message="M", timestamp=1.0, source="ci")
        self.assertEqual(n.source, "ci")


class TestNotificationQueue(unittest.TestCase):
    def setUp(self):
        self.q = NotificationQueue(max_size=5)

    def test_push_returns_notification(self):
        n = self.q.push("info", "Hello", "World")
        self.assertIsInstance(n, Notification)
        self.assertEqual(n.level, "info")
        self.assertEqual(n.title, "Hello")

    def test_push_invalid_level(self):
        with self.assertRaises(ValueError):
            self.q.push("critical", "T", "M")

    def test_push_auto_id(self):
        n1 = self.q.push("info", "A", "B")
        n2 = self.q.push("info", "C", "D")
        self.assertNotEqual(n1.id, n2.id)

    def test_push_custom_source(self):
        n = self.q.push("warning", "T", "M", source="plugin")
        self.assertEqual(n.source, "plugin")

    def test_total_count(self):
        self.assertEqual(self.q.total_count, 0)
        self.q.push("info", "A", "B")
        self.assertEqual(self.q.total_count, 1)

    def test_unread_count(self):
        self.q.push("info", "A", "B")
        self.q.push("error", "C", "D")
        self.assertEqual(self.q.unread_count, 2)

    def test_pop_returns_oldest_unread(self):
        self.q.push("info", "First", "1")
        self.q.push("info", "Second", "2")
        n = self.q.pop()
        self.assertEqual(n.title, "First")
        self.assertTrue(n.read)

    def test_pop_empty(self):
        self.assertIsNone(self.q.pop())

    def test_pop_all_read(self):
        self.q.push("info", "A", "B")
        self.q.pop()
        self.assertIsNone(self.q.pop())

    def test_peek_does_not_mark_read(self):
        self.q.push("info", "A", "B")
        n = self.q.peek()
        self.assertFalse(n.read)
        self.assertEqual(self.q.unread_count, 1)

    def test_peek_empty(self):
        self.assertIsNone(self.q.peek())

    def test_mark_read(self):
        n = self.q.push("info", "A", "B")
        self.assertTrue(self.q.mark_read(n.id))
        self.assertEqual(self.q.unread_count, 0)

    def test_mark_read_not_found(self):
        self.assertFalse(self.q.mark_read("nonexistent"))

    def test_mark_all_read(self):
        self.q.push("info", "A", "B")
        self.q.push("error", "C", "D")
        self.q.mark_all_read()
        self.assertEqual(self.q.unread_count, 0)

    def test_by_level(self):
        self.q.push("info", "A", "B")
        self.q.push("error", "C", "D")
        self.q.push("info", "E", "F")
        infos = self.q.by_level("info")
        self.assertEqual(len(infos), 2)
        errors = self.q.by_level("error")
        self.assertEqual(len(errors), 1)

    def test_clear_read(self):
        self.q.push("info", "A", "B")
        n2 = self.q.push("info", "C", "D")
        self.q.pop()  # marks first as read
        self.q.clear_read()
        self.assertEqual(self.q.total_count, 1)
        self.assertEqual(self.q.peek().title, "C")

    def test_max_size_eviction(self):
        for i in range(7):
            self.q.push("info", f"N{i}", "msg")
        self.assertEqual(self.q.total_count, 5)

    def test_timestamp_is_set(self):
        before = time.time()
        n = self.q.push("info", "T", "M")
        after = time.time()
        self.assertGreaterEqual(n.timestamp, before)
        self.assertLessEqual(n.timestamp, after)

    def test_valid_levels(self):
        for level in ("info", "warning", "error", "success"):
            n = self.q.push(level, "T", "M")
            self.assertEqual(n.level, level)


if __name__ == "__main__":
    unittest.main()
