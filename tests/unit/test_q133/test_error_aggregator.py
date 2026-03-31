"""Tests for Q133 ErrorAggregator."""
from __future__ import annotations
import time
import unittest
from lidco.debug.error_aggregator import ErrorAggregator, ErrorRecord


class TestErrorRecord(unittest.TestCase):
    def test_defaults(self):
        rec = ErrorRecord(id="1", error_type="ValueError", message="bad")
        self.assertEqual(rec.count, 1)
        self.assertEqual(rec.context, {})


class TestErrorAggregator(unittest.TestCase):
    def setUp(self):
        self.agg = ErrorAggregator()

    def test_record_single(self):
        rec = self.agg.record(ValueError("bad value"))
        self.assertEqual(rec.error_type, "ValueError")
        self.assertEqual(rec.message, "bad value")
        self.assertEqual(rec.count, 1)

    def test_record_increments_count(self):
        for _ in range(3):
            self.agg.record(ValueError("same error"))
        rec = self.agg.get_all()[0]
        self.assertEqual(rec.count, 3)

    def test_record_different_errors(self):
        self.agg.record(ValueError("v"))
        self.agg.record(TypeError("t"))
        self.assertEqual(len(self.agg.get_all()), 2)

    def test_record_same_type_different_message(self):
        self.agg.record(ValueError("msg1"))
        self.agg.record(ValueError("msg2"))
        self.assertEqual(len(self.agg.get_all()), 2)

    def test_record_with_context(self):
        rec = self.agg.record(RuntimeError("oops"), context={"file": "main.py"})
        self.assertEqual(rec.context["file"], "main.py")

    def test_first_seen_set(self):
        before = time.time()
        self.agg.record(ValueError("x"))
        rec = self.agg.get_all()[0]
        self.assertGreaterEqual(rec.first_seen, before)

    def test_last_seen_updated(self):
        self.agg.record(ValueError("x"))
        first_last = self.agg.get_all()[0].last_seen
        self.agg.record(ValueError("x"))
        second_last = self.agg.get_all()[0].last_seen
        self.assertGreaterEqual(second_last, first_last)

    def test_first_seen_not_updated_on_repeat(self):
        self.agg.record(ValueError("x"))
        first_seen = self.agg.get_all()[0].first_seen
        self.agg.record(ValueError("x"))
        self.assertEqual(self.agg.get_all()[0].first_seen, first_seen)

    def test_get_all_empty(self):
        self.assertEqual(self.agg.get_all(), [])

    def test_top_by_count(self):
        self.agg.record(ValueError("common"))
        self.agg.record(ValueError("common"))
        self.agg.record(ValueError("common"))
        self.agg.record(TypeError("rare"))
        top = self.agg.top(1)
        self.assertEqual(top[0].message, "common")

    def test_top_n(self):
        for i in range(5):
            for _ in range(i + 1):
                self.agg.record(ValueError(f"error{i}"))
        top = self.agg.top(3)
        self.assertEqual(len(top), 3)

    def test_since_filters(self):
        self.agg.record(ValueError("old"))
        marker = time.time()
        self.agg.record(RuntimeError("new"))
        recent = self.agg.since(marker)
        types = [r.error_type for r in recent]
        self.assertIn("RuntimeError", types)

    def test_clear(self):
        self.agg.record(ValueError("x"))
        self.agg.clear()
        self.assertEqual(self.agg.get_all(), [])

    def test_summary_empty(self):
        s = self.agg.summary()
        self.assertEqual(s["total_records"], 0)
        self.assertEqual(s["total_occurrences"], 0)
        self.assertEqual(s["types"], {})

    def test_summary_counts(self):
        for _ in range(3):
            self.agg.record(ValueError("x"))
        self.agg.record(TypeError("y"))
        s = self.agg.summary()
        self.assertEqual(s["total_records"], 2)
        self.assertEqual(s["total_occurrences"], 4)
        self.assertEqual(s["types"]["ValueError"], 3)
        self.assertEqual(s["types"]["TypeError"], 1)

    def test_record_returns_same_record_on_repeat(self):
        r1 = self.agg.record(ValueError("same"))
        r2 = self.agg.record(ValueError("same"))
        self.assertEqual(r1.id, r2.id)

    def test_record_id_unique_per_error(self):
        r1 = self.agg.record(ValueError("x"))
        r2 = self.agg.record(TypeError("y"))
        self.assertNotEqual(r1.id, r2.id)


if __name__ == "__main__":
    unittest.main()
