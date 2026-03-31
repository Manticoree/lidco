"""Tests for NotificationHistory (Task 870)."""
from __future__ import annotations

import time
import unittest

from lidco.alerts.notification_queue import Notification
from lidco.alerts.notification_history import HistoryQuery, NotificationHistory


def _make_notif(level="info", title="T", message="M", source="system", ts=None):
    return Notification(
        id="n" + str(id(object())),
        level=level,
        title=title,
        message=message,
        timestamp=ts or time.time(),
        source=source,
    )


class TestHistoryQuery(unittest.TestCase):
    def test_defaults(self):
        q = HistoryQuery()
        self.assertIsNone(q.level)
        self.assertIsNone(q.source)
        self.assertEqual(q.limit, 50)


class TestNotificationHistory(unittest.TestCase):
    def setUp(self):
        self.hist = NotificationHistory(max_entries=10)

    def test_record_and_query(self):
        n = _make_notif()
        self.hist.record(n)
        results = self.hist.query()
        self.assertEqual(len(results), 1)

    def test_query_no_filter(self):
        for _ in range(3):
            self.hist.record(_make_notif())
        self.assertEqual(len(self.hist.query()), 3)

    def test_query_by_level(self):
        self.hist.record(_make_notif(level="info"))
        self.hist.record(_make_notif(level="error"))
        q = HistoryQuery(level="error")
        results = self.hist.query(q)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].level, "error")

    def test_query_by_source(self):
        self.hist.record(_make_notif(source="ci"))
        self.hist.record(_make_notif(source="system"))
        q = HistoryQuery(source="ci")
        results = self.hist.query(q)
        self.assertEqual(len(results), 1)

    def test_query_since(self):
        old = _make_notif(ts=100.0)
        new = _make_notif(ts=200.0)
        self.hist.record(old)
        self.hist.record(new)
        q = HistoryQuery(since=150.0)
        results = self.hist.query(q)
        self.assertEqual(len(results), 1)

    def test_query_until(self):
        old = _make_notif(ts=100.0)
        new = _make_notif(ts=200.0)
        self.hist.record(old)
        self.hist.record(new)
        q = HistoryQuery(until=150.0)
        results = self.hist.query(q)
        self.assertEqual(len(results), 1)

    def test_query_limit(self):
        for _ in range(5):
            self.hist.record(_make_notif())
        q = HistoryQuery(limit=2)
        results = self.hist.query(q)
        self.assertEqual(len(results), 2)

    def test_stats_empty(self):
        s = self.hist.stats()
        self.assertEqual(s["total"], 0)
        self.assertIsNone(s["earliest"])

    def test_stats_populated(self):
        self.hist.record(_make_notif(level="info", ts=100.0))
        self.hist.record(_make_notif(level="error", ts=200.0))
        self.hist.record(_make_notif(level="info", ts=300.0))
        s = self.hist.stats()
        self.assertEqual(s["total"], 3)
        self.assertEqual(s["by_level"]["info"], 2)
        self.assertEqual(s["by_level"]["error"], 1)
        self.assertEqual(s["earliest"], 100.0)
        self.assertEqual(s["latest"], 300.0)

    def test_export(self):
        self.hist.record(_make_notif(title="Test"))
        exported = self.hist.export()
        self.assertEqual(len(exported), 1)
        self.assertIn("id", exported[0])
        self.assertEqual(exported[0]["title"], "Test")

    def test_export_empty(self):
        self.assertEqual(self.hist.export(), [])

    def test_clear_all(self):
        self.hist.record(_make_notif())
        self.hist.clear()
        self.assertEqual(len(self.hist.query()), 0)

    def test_clear_before(self):
        self.hist.record(_make_notif(ts=100.0))
        self.hist.record(_make_notif(ts=200.0))
        self.hist.clear(before=150.0)
        results = self.hist.query()
        self.assertEqual(len(results), 1)

    def test_search_in_title(self):
        self.hist.record(_make_notif(title="Build failed"))
        self.hist.record(_make_notif(title="Deploy OK"))
        results = self.hist.search("build")
        self.assertEqual(len(results), 1)

    def test_search_in_message(self):
        self.hist.record(_make_notif(message="error in module X"))
        results = self.hist.search("module")
        self.assertEqual(len(results), 1)

    def test_search_case_insensitive(self):
        self.hist.record(_make_notif(title="ERROR"))
        results = self.hist.search("error")
        self.assertEqual(len(results), 1)

    def test_search_no_match(self):
        self.hist.record(_make_notif(title="hello"))
        results = self.hist.search("xyz")
        self.assertEqual(len(results), 0)

    def test_max_entries_eviction(self):
        for i in range(15):
            self.hist.record(_make_notif(title=f"N{i}"))
        self.assertEqual(len(self.hist.query(HistoryQuery(limit=100))), 10)


if __name__ == "__main__":
    unittest.main()
