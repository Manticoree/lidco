"""Tests for lidco.notify.history."""
from __future__ import annotations

import json
import time
import unittest

from lidco.notify.history import HistoryEntry, NotificationHistory


class TestHistoryEntry(unittest.TestCase):
    def test_defaults(self):
        e = HistoryEntry(id="x", title="T", message="M", level="info", timestamp=1.0)
        self.assertFalse(e.dismissed)
        self.assertIsNone(e.snoozed_until)


class TestNotificationHistory(unittest.TestCase):
    def test_add_returns_entry(self):
        h = NotificationHistory()
        e = h.add("T", "M")
        self.assertEqual(e.title, "T")
        self.assertEqual(e.message, "M")
        self.assertEqual(e.level, "info")
        self.assertGreater(e.timestamp, 0)

    def test_add_custom_level(self):
        h = NotificationHistory()
        e = h.add("T", "M", level="error")
        self.assertEqual(e.level, "error")

    def test_get_found(self):
        h = NotificationHistory()
        e = h.add("T", "M")
        found = h.get(e.id)
        self.assertIsNotNone(found)
        self.assertEqual(found.id, e.id)

    def test_get_not_found(self):
        h = NotificationHistory()
        self.assertIsNone(h.get("nonexistent"))

    def test_dismiss(self):
        h = NotificationHistory()
        e = h.add("T", "M")
        self.assertTrue(h.dismiss(e.id))
        self.assertTrue(h.get(e.id).dismissed)

    def test_dismiss_not_found(self):
        h = NotificationHistory()
        self.assertFalse(h.dismiss("nope"))

    def test_snooze(self):
        h = NotificationHistory()
        e = h.add("T", "M")
        self.assertTrue(h.snooze(e.id, 60.0))
        self.assertIsNotNone(h.get(e.id).snoozed_until)

    def test_snooze_not_found(self):
        h = NotificationHistory()
        self.assertFalse(h.snooze("nope", 10.0))

    def test_search(self):
        h = NotificationHistory()
        h.add("Build Failed", "Error in main.py")
        h.add("Tests Passed", "All green")
        results = h.search("build")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Build Failed")

    def test_search_case_insensitive(self):
        h = NotificationHistory()
        h.add("Error", "CRITICAL failure")
        results = h.search("critical")
        self.assertEqual(len(results), 1)

    def test_undismissed(self):
        h = NotificationHistory()
        e1 = h.add("A", "a")
        e2 = h.add("B", "b")
        h.dismiss(e1.id)
        undismissed = h.undismissed()
        self.assertEqual(len(undismissed), 1)
        self.assertEqual(undismissed[0].id, e2.id)

    def test_undismissed_excludes_snoozed(self):
        h = NotificationHistory()
        e = h.add("A", "a")
        h.snooze(e.id, 9999.0)
        self.assertEqual(len(h.undismissed()), 0)

    def test_undismissed_includes_expired_snooze(self):
        h = NotificationHistory()
        e = h.add("A", "a")
        h.snooze(e.id, 0.01)
        time.sleep(0.02)
        self.assertEqual(len(h.undismissed()), 1)

    def test_clear(self):
        h = NotificationHistory()
        h.add("A", "a")
        h.add("B", "b")
        count = h.clear()
        self.assertEqual(count, 2)
        self.assertEqual(len(h.all_entries()), 0)

    def test_max_entries(self):
        h = NotificationHistory(max_entries=3)
        for i in range(5):
            h.add(f"T{i}", f"M{i}")
        self.assertEqual(len(h.all_entries()), 3)
        self.assertEqual(h.all_entries()[0].title, "T2")

    def test_export_json(self):
        h = NotificationHistory()
        h.add("T", "M")
        data = json.loads(h.export("json"))
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "T")

    def test_export_csv(self):
        h = NotificationHistory()
        h.add("T", "M")
        csv = h.export("csv")
        self.assertIn("id,title,message", csv)
        self.assertIn("T,M", csv)

    def test_all_entries_is_copy(self):
        h = NotificationHistory()
        h.add("T", "M")
        entries = h.all_entries()
        entries.clear()
        self.assertEqual(len(h.all_entries()), 1)

    def test_summary(self):
        h = NotificationHistory()
        h.add("A", "a")
        e = h.add("B", "b")
        h.dismiss(e.id)
        s = h.summary()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["dismissed"], 1)
        self.assertEqual(s["max_entries"], 1000)


if __name__ == "__main__":
    unittest.main()
