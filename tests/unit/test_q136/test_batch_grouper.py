"""Tests for BatchGrouper."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch
from lidco.scheduling.batch_grouper import Batch, BatchGrouper


class TestBatch(unittest.TestCase):
    def test_fields(self):
        b = Batch(id="abc", group_key="g", items=[1, 2], created_at=0.0)
        self.assertEqual(b.group_key, "g")
        self.assertEqual(len(b.items), 2)


class TestBatchGrouper(unittest.TestCase):
    def setUp(self):
        self.bg = BatchGrouper(max_batch_size=3, max_wait_seconds=60.0)

    def test_add_returns_none_below_size(self):
        result = self.bg.add("item1", "g1")
        self.assertIsNone(result)

    def test_add_returns_batch_at_max_size(self):
        self.bg.add("a", "g1")
        self.bg.add("b", "g1")
        batch = self.bg.add("c", "g1")
        self.assertIsNotNone(batch)
        self.assertIsInstance(batch, Batch)
        self.assertEqual(len(batch.items), 3)
        self.assertEqual(batch.group_key, "g1")

    def test_add_default_group_key(self):
        self.bg.add("a")
        self.assertEqual(self.bg.pending_count("default"), 1)

    def test_add_time_trigger(self):
        bg = BatchGrouper(max_batch_size=100, max_wait_seconds=0.0)
        bg.add("first", "g")
        # second add should trigger since max_wait is 0
        batch = bg.add("second", "g")
        self.assertIsNotNone(batch)

    def test_flush_single_group(self):
        self.bg.add("a", "g1")
        self.bg.add("b", "g1")
        batches = self.bg.flush("g1")
        self.assertEqual(len(batches), 1)
        self.assertEqual(len(batches[0].items), 2)

    def test_flush_all_groups(self):
        self.bg.add("a", "g1")
        self.bg.add("b", "g2")
        batches = self.bg.flush()
        self.assertEqual(len(batches), 2)

    def test_flush_empty_returns_empty(self):
        self.assertEqual(self.bg.flush(), [])

    def test_flush_nonexistent_group(self):
        self.assertEqual(self.bg.flush("nope"), [])

    def test_pending_count_total(self):
        self.bg.add("a", "g1")
        self.bg.add("b", "g2")
        self.assertEqual(self.bg.pending_count(), 2)

    def test_pending_count_specific_group(self):
        self.bg.add("a", "g1")
        self.bg.add("b", "g1")
        self.bg.add("c", "g2")
        self.assertEqual(self.bg.pending_count("g1"), 2)
        self.assertEqual(self.bg.pending_count("g2"), 1)

    def test_pending_count_empty_group(self):
        self.assertEqual(self.bg.pending_count("nope"), 0)

    def test_stats_initial(self):
        s = self.bg.stats()
        self.assertEqual(s["batches_created"], 0)
        self.assertEqual(s["items_processed"], 0)
        self.assertEqual(s["groups"], [])

    def test_stats_after_batch(self):
        for i in range(3):
            self.bg.add(f"item{i}", "g1")
        s = self.bg.stats()
        self.assertEqual(s["batches_created"], 1)
        self.assertEqual(s["items_processed"], 3)

    def test_stats_groups_tracked(self):
        self.bg.add("a", "g1")
        self.bg.add("b", "g2")
        s = self.bg.stats()
        self.assertIn("g1", s["groups"])
        self.assertIn("g2", s["groups"])

    def test_batch_has_unique_id(self):
        bg = BatchGrouper(max_batch_size=1)
        b1 = bg.add("a", "g")
        b2 = bg.add("b", "g")
        self.assertNotEqual(b1.id, b2.id)

    def test_after_flush_pending_is_zero(self):
        self.bg.add("a", "g1")
        self.bg.flush("g1")
        self.assertEqual(self.bg.pending_count("g1"), 0)

    def test_multiple_batches_same_group(self):
        for i in range(6):
            self.bg.add(f"item{i}", "g1")
        s = self.bg.stats()
        self.assertEqual(s["batches_created"], 2)
        self.assertEqual(s["items_processed"], 6)

    def test_flush_updates_stats(self):
        self.bg.add("a", "g1")
        self.bg.flush("g1")
        s = self.bg.stats()
        self.assertEqual(s["batches_created"], 1)
        self.assertEqual(s["items_processed"], 1)


if __name__ == "__main__":
    unittest.main()
