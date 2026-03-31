"""Tests for Q133 StateInspector."""
from __future__ import annotations
import unittest
from lidco.debug.state_inspector import StateInspector, StateSnapshot


class TestStateSnapshot(unittest.TestCase):
    def test_fields(self):
        snap = StateSnapshot(id="1", label="test", data={"x": 1}, timestamp=0.0)
        self.assertEqual(snap.label, "test")
        self.assertEqual(snap.data["x"], 1)


class TestStateInspector(unittest.TestCase):
    def setUp(self):
        self.inspector = StateInspector()

    def test_capture_returns_snapshot(self):
        snap = self.inspector.capture({"x": 1})
        self.assertIsInstance(snap, StateSnapshot)

    def test_capture_stores_data(self):
        snap = self.inspector.capture({"key": "value"})
        self.assertEqual(snap.data["key"], "value")

    def test_capture_label(self):
        snap = self.inspector.capture({}, label="my_label")
        self.assertEqual(snap.label, "my_label")

    def test_capture_timestamp(self):
        snap = self.inspector.capture({})
        self.assertGreater(snap.timestamp, 0.0)

    def test_capture_unique_ids(self):
        snap1 = self.inspector.capture({})
        snap2 = self.inspector.capture({})
        self.assertNotEqual(snap1.id, snap2.id)

    def test_diff_added(self):
        a = self.inspector.capture({"x": 1})
        b = self.inspector.capture({"x": 1, "y": 2})
        diff = self.inspector.diff(a, b)
        self.assertEqual(diff["added"], {"y": 2})

    def test_diff_removed(self):
        a = self.inspector.capture({"x": 1, "y": 2})
        b = self.inspector.capture({"x": 1})
        diff = self.inspector.diff(a, b)
        self.assertEqual(diff["removed"], {"y": 2})

    def test_diff_changed(self):
        a = self.inspector.capture({"x": 1})
        b = self.inspector.capture({"x": 2})
        diff = self.inspector.diff(a, b)
        self.assertEqual(diff["changed"], {"x": (1, 2)})

    def test_diff_no_change(self):
        a = self.inspector.capture({"x": 1})
        b = self.inspector.capture({"x": 1})
        diff = self.inspector.diff(a, b)
        self.assertEqual(diff["added"], {})
        self.assertEqual(diff["removed"], {})
        self.assertEqual(diff["changed"], {})

    def test_list_snapshots_empty(self):
        self.assertEqual(self.inspector.list_snapshots(), [])

    def test_list_snapshots(self):
        self.inspector.capture({"a": 1})
        self.inspector.capture({"b": 2})
        self.assertEqual(len(self.inspector.list_snapshots()), 2)

    def test_get_by_id(self):
        snap = self.inspector.capture({"x": 42})
        retrieved = self.inspector.get(snap.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.data["x"], 42)

    def test_get_missing_id(self):
        self.assertIsNone(self.inspector.get("nonexistent"))

    def test_clear(self):
        self.inspector.capture({"x": 1})
        self.inspector.clear()
        self.assertEqual(len(self.inspector.list_snapshots()), 0)
        self.assertIsNone(self.inspector.get("any"))

    def test_replay_empty(self):
        diffs = self.inspector.replay([])
        self.assertEqual(diffs, [])

    def test_replay_single(self):
        snap = self.inspector.capture({"x": 1})
        diffs = self.inspector.replay([snap])
        self.assertEqual(diffs, [])

    def test_replay_two_snaps(self):
        s1 = self.inspector.capture({"x": 1})
        s2 = self.inspector.capture({"x": 2})
        diffs = self.inspector.replay([s1, s2])
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0]["changed"]["x"], (1, 2))

    def test_replay_three_snaps(self):
        s1 = self.inspector.capture({"x": 1})
        s2 = self.inspector.capture({"x": 2})
        s3 = self.inspector.capture({"x": 2, "y": 3})
        diffs = self.inspector.replay([s1, s2, s3])
        self.assertEqual(len(diffs), 2)

    def test_data_is_copy(self):
        original = {"x": 1}
        snap = self.inspector.capture(original)
        original["x"] = 99
        self.assertEqual(snap.data["x"], 1)


if __name__ == "__main__":
    unittest.main()
