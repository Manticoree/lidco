"""Tests for QueueOverflowGuard (Q343, Task 3)."""
from __future__ import annotations

import unittest

from lidco.stability.queue_guard import QueueOverflowGuard


class TestMonitorDepth(unittest.TestCase):
    def setUp(self):
        self.guard = QueueOverflowGuard(max_depth=1000)

    def test_low_depth_is_ok(self):
        results = self.guard.monitor_depth({"q1": 100})
        self.assertEqual(results[0]["status"], "ok")

    def test_warning_threshold(self):
        # 75%+ of max_depth => warning
        results = self.guard.monitor_depth({"q1": 760})
        self.assertEqual(results[0]["status"], "warning")

    def test_critical_threshold(self):
        # 90%+ of max_depth => critical
        results = self.guard.monitor_depth({"q1": 950})
        self.assertEqual(results[0]["status"], "critical")

    def test_result_has_required_keys(self):
        results = self.guard.monitor_depth({"q1": 10})
        r = results[0]
        self.assertIn("queue_name", r)
        self.assertIn("current_size", r)
        self.assertIn("max_depth", r)
        self.assertIn("status", r)

    def test_multiple_queues(self):
        results = self.guard.monitor_depth({"q1": 10, "q2": 900, "q3": 760})
        statuses = {r["queue_name"]: r["status"] for r in results}
        self.assertEqual(statuses["q1"], "ok")
        self.assertEqual(statuses["q2"], "critical")
        self.assertEqual(statuses["q3"], "warning")

    def test_empty_dict_returns_empty(self):
        results = self.guard.monitor_depth({})
        self.assertEqual(results, [])


class TestDetectBackpressure(unittest.TestCase):
    def setUp(self):
        self.guard = QueueOverflowGuard()

    def test_producer_faster_has_backpressure(self):
        result = self.guard.detect_backpressure(100.0, 50.0)
        self.assertTrue(result["has_backpressure"])

    def test_consumer_faster_no_backpressure(self):
        result = self.guard.detect_backpressure(50.0, 100.0)
        self.assertFalse(result["has_backpressure"])

    def test_equal_rates_no_backpressure(self):
        result = self.guard.detect_backpressure(100.0, 100.0)
        self.assertFalse(result["has_backpressure"])

    def test_zero_consumer_infinite_ratio(self):
        result = self.guard.detect_backpressure(10.0, 0.0)
        self.assertTrue(result["has_backpressure"])
        self.assertEqual(result["ratio"], float("inf"))

    def test_result_has_required_keys(self):
        result = self.guard.detect_backpressure(10.0, 5.0)
        self.assertIn("has_backpressure", result)
        self.assertIn("producer_rate", result)
        self.assertIn("consumer_rate", result)
        self.assertIn("ratio", result)
        self.assertIn("suggestion", result)

    def test_suggestion_non_empty(self):
        result = self.guard.detect_backpressure(200.0, 10.0)
        self.assertTrue(len(result["suggestion"]) > 0)


class TestCheckOverflowPrevention(unittest.TestCase):
    def setUp(self):
        self.guard = QueueOverflowGuard()

    def test_unbounded_queue_flagged(self):
        src = "import queue\nq = queue.Queue()\n"
        results = self.guard.check_overflow_prevention(src)
        self.assertTrue(len(results) >= 1)
        self.assertFalse(results[0]["has_maxsize"])

    def test_bounded_queue_ok(self):
        src = "import queue\nq = queue.Queue(maxsize=100)\n"
        results = self.guard.check_overflow_prevention(src)
        self.assertTrue(len(results) >= 1)
        self.assertTrue(results[0]["has_maxsize"])

    def test_asyncio_queue_without_maxsize_flagged(self):
        src = "import asyncio\nq = asyncio.Queue()\n"
        results = self.guard.check_overflow_prevention(src)
        self.assertTrue(len(results) >= 1)
        self.assertFalse(results[0]["has_maxsize"])

    def test_result_has_required_keys(self):
        src = "import queue\nq = queue.Queue()\n"
        results = self.guard.check_overflow_prevention(src)
        if results:
            r = results[0]
            self.assertIn("line", r)
            self.assertIn("queue_type", r)
            self.assertIn("has_maxsize", r)
            self.assertIn("suggestion", r)

    def test_suggestion_mentions_maxsize_for_unbounded(self):
        src = "import queue\nq = queue.Queue()\n"
        results = self.guard.check_overflow_prevention(src)
        if results and not results[0]["has_maxsize"]:
            self.assertIn("maxsize", results[0]["suggestion"].lower())

    def test_no_queues_returns_empty(self):
        src = "x = 1\n"
        results = self.guard.check_overflow_prevention(src)
        self.assertEqual(results, [])


class TestDetectConsumerLag(unittest.TestCase):
    def setUp(self):
        self.guard = QueueOverflowGuard(max_depth=1000)

    def test_no_lag_when_consumed_equals_produced(self):
        result = self.guard.detect_consumer_lag(100, 100, 10.0)
        self.assertEqual(result["lag"], 0)
        self.assertEqual(result["alert_level"], "none")

    def test_lag_computed_correctly(self):
        result = self.guard.detect_consumer_lag(200, 100, 10.0)
        self.assertEqual(result["lag"], 100)

    def test_critical_when_time_to_overflow_low(self):
        # lag=900, lag_rate=90/s, max_depth=1000, remaining=100, time=100/90 ~1.1s < 60s
        result = self.guard.detect_consumer_lag(900, 0, 10.0)
        self.assertEqual(result["alert_level"], "critical")

    def test_result_has_required_keys(self):
        result = self.guard.detect_consumer_lag(50, 30, 5.0)
        self.assertIn("lag", result)
        self.assertIn("lag_rate", result)
        self.assertIn("time_to_overflow", result)
        self.assertIn("alert_level", result)

    def test_time_to_overflow_none_when_no_lag(self):
        result = self.guard.detect_consumer_lag(100, 100, 10.0)
        self.assertIsNone(result["time_to_overflow"])
