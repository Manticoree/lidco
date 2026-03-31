"""Tests for AutoCheckpoint."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from lidco.resilience.auto_checkpoint import AutoCheckpoint, Checkpoint


class TestAutoCheckpoint(unittest.TestCase):
    def setUp(self):
        self.cp = AutoCheckpoint(max_checkpoints=5, interval_seconds=10.0)

    # --- save ---
    def test_save_returns_checkpoint(self):
        result = self.cp.save("test", {"key": "value"})
        self.assertIsInstance(result, Checkpoint)

    def test_save_sets_label(self):
        result = self.cp.save("my_label", {})
        self.assertEqual(result.label, "my_label")

    def test_save_sets_id(self):
        result = self.cp.save("x", {})
        self.assertIsInstance(result.id, str)
        self.assertTrue(len(result.id) > 0)

    def test_save_sets_timestamp(self):
        before = time.time()
        result = self.cp.save("x", {})
        after = time.time()
        self.assertGreaterEqual(result.timestamp, before)
        self.assertLessEqual(result.timestamp, after)

    def test_save_stores_data(self):
        data = {"a": 1, "b": [2, 3]}
        result = self.cp.save("x", data)
        self.assertEqual(result.data, data)

    def test_save_computes_size(self):
        result = self.cp.save("x", {"key": "val"})
        self.assertGreater(result.size_bytes, 0)

    def test_save_increments_count(self):
        self.cp.save("a", {})
        self.cp.save("b", {})
        self.assertEqual(len(self.cp.list_checkpoints()), 2)

    # --- latest ---
    def test_latest_empty(self):
        self.assertIsNone(self.cp.latest())

    def test_latest_returns_most_recent(self):
        self.cp.save("first", {"n": 1})
        self.cp.save("second", {"n": 2})
        latest = self.cp.latest()
        self.assertEqual(latest.label, "second")

    # --- list_checkpoints ---
    def test_list_empty(self):
        self.assertEqual(self.cp.list_checkpoints(), [])

    def test_list_newest_first(self):
        self.cp.save("a", {})
        self.cp.save("b", {})
        self.cp.save("c", {})
        result = self.cp.list_checkpoints()
        self.assertEqual(result[0].label, "c")
        self.assertEqual(result[2].label, "a")

    # --- restore ---
    def test_restore_valid_id(self):
        cp = self.cp.save("x", {"key": "val"})
        data = self.cp.restore(cp.id)
        self.assertEqual(data, {"key": "val"})

    def test_restore_invalid_id(self):
        self.assertIsNone(self.cp.restore("nonexistent"))

    # --- cleanup ---
    def test_cleanup_trims_to_max(self):
        for i in range(8):
            self.cp.save(f"cp_{i}", {"i": i})
        # max is 5
        self.assertEqual(len(self.cp.list_checkpoints()), 5)

    def test_cleanup_keeps_newest(self):
        for i in range(8):
            self.cp.save(f"cp_{i}", {"i": i})
        result = self.cp.list_checkpoints()
        self.assertEqual(result[0].label, "cp_7")

    # --- should_save ---
    def test_should_save_not_elapsed(self):
        self.assertFalse(self.cp.should_save(time.time()))

    def test_should_save_elapsed(self):
        self.assertTrue(self.cp.should_save(time.time() - 20.0))

    def test_should_save_exact_boundary(self):
        # At exactly interval_seconds ago => should save
        self.assertTrue(self.cp.should_save(time.time() - 10.0))

    # --- clear ---
    def test_clear_removes_all(self):
        self.cp.save("a", {})
        self.cp.save("b", {})
        self.cp.clear()
        self.assertEqual(len(self.cp.list_checkpoints()), 0)

    def test_clear_latest_is_none(self):
        self.cp.save("a", {})
        self.cp.clear()
        self.assertIsNone(self.cp.latest())

    # --- edge cases ---
    def test_unique_ids(self):
        cp1 = self.cp.save("a", {})
        cp2 = self.cp.save("b", {})
        self.assertNotEqual(cp1.id, cp2.id)

    def test_max_checkpoints_one(self):
        cp = AutoCheckpoint(max_checkpoints=1)
        cp.save("a", {})
        cp.save("b", {})
        self.assertEqual(len(cp.list_checkpoints()), 1)
        self.assertEqual(cp.latest().label, "b")


if __name__ == "__main__":
    unittest.main()
