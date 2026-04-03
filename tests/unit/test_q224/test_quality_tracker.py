"""Tests for lidco.routing.quality_tracker."""
from __future__ import annotations

import unittest

from lidco.routing.quality_tracker import QualityRecord, QualityTracker


class TestQualityRecord(unittest.TestCase):
    def test_defaults(self) -> None:
        r = QualityRecord(model="m", score=0.8)
        self.assertEqual(r.task_type, "general")
        self.assertGreater(r.timestamp, 0)

    def test_custom_task_type(self) -> None:
        r = QualityRecord(model="m", score=0.5, task_type="coding")
        self.assertEqual(r.task_type, "coding")


class TestQualityTracker(unittest.TestCase):
    def setUp(self) -> None:
        self.tracker = QualityTracker()

    def test_record_returns_record(self) -> None:
        rec = self.tracker.record("m1", 0.9)
        self.assertIsInstance(rec, QualityRecord)
        self.assertEqual(rec.model, "m1")
        self.assertEqual(rec.score, 0.9)

    def test_average_no_records(self) -> None:
        self.assertIsNone(self.tracker.average("m1"))

    def test_average_single(self) -> None:
        self.tracker.record("m1", 0.8)
        self.assertAlmostEqual(self.tracker.average("m1"), 0.8)

    def test_average_multiple(self) -> None:
        self.tracker.record("m1", 0.6)
        self.tracker.record("m1", 0.8)
        self.assertAlmostEqual(self.tracker.average("m1"), 0.7)

    def test_average_by_task_type(self) -> None:
        self.tracker.record("m1", 0.9, "coding")
        self.tracker.record("m1", 0.5, "chat")
        self.assertAlmostEqual(self.tracker.average("m1", "coding"), 0.9)
        self.assertAlmostEqual(self.tracker.average("m1", "chat"), 0.5)

    def test_compare_both_present(self) -> None:
        self.tracker.record("a", 0.9)
        self.tracker.record("b", 0.7)
        cmp = self.tracker.compare("a", "b")
        self.assertEqual(cmp["winner"], "a")
        self.assertAlmostEqual(cmp["model_a"], 0.9)
        self.assertAlmostEqual(cmp["model_b"], 0.7)

    def test_compare_one_missing(self) -> None:
        self.tracker.record("a", 0.8)
        cmp = self.tracker.compare("a", "b")
        self.assertEqual(cmp["winner"], "a")
        self.assertIsNone(cmp["model_b"])

    def test_compare_both_missing(self) -> None:
        cmp = self.tracker.compare("x", "y")
        self.assertIsNone(cmp["winner"])

    def test_detect_regression_not_enough_data(self) -> None:
        self.tracker.record("m", 0.5)
        self.assertFalse(self.tracker.detect_regression("m"))

    def test_detect_regression_true(self) -> None:
        # first half: high scores; second half: low scores
        for _ in range(5):
            self.tracker.record("m", 0.9)
        for _ in range(5):
            self.tracker.record("m", 0.3)
        self.assertTrue(self.tracker.detect_regression("m", threshold=0.1))

    def test_detect_regression_false(self) -> None:
        for _ in range(10):
            self.tracker.record("m", 0.8)
        self.assertFalse(self.tracker.detect_regression("m"))

    def test_summary(self) -> None:
        self.tracker.record("m1", 0.9)
        self.tracker.record("m2", 0.7)
        s = self.tracker.summary()
        self.assertIn("m1", s)
        self.assertIn("m2", s)
        self.assertEqual(s["m1"]["count"], 1)

    def test_records_all(self) -> None:
        self.tracker.record("a", 0.5)
        self.tracker.record("b", 0.6)
        self.assertEqual(len(self.tracker.records()), 2)

    def test_records_filtered(self) -> None:
        self.tracker.record("a", 0.5)
        self.tracker.record("b", 0.6)
        self.assertEqual(len(self.tracker.records("a")), 1)

    def test_window_trimming(self) -> None:
        tracker = QualityTracker(window_size=5)
        for i in range(10):
            tracker.record("m", float(i) / 10)
        self.assertEqual(len(tracker.records()), 5)


if __name__ == "__main__":
    unittest.main()
