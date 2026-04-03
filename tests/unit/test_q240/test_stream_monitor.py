"""Tests for lidco.streaming.stream_monitor — StreamMonitor."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from lidco.streaming.stream_monitor import StreamMonitor


class TestStreamMonitorInit(unittest.TestCase):
    def test_initial_state(self):
        m = StreamMonitor()
        self.assertEqual(m.tokens_per_second(), 0.0)
        self.assertFalse(m.detect_stall())
        self.assertEqual(m.stats()["total_tokens"], 0)


class TestRecord(unittest.TestCase):
    def test_record_increments_count(self):
        m = StreamMonitor()
        m.record("a")
        m.record("b")
        self.assertEqual(m.stats()["total_tokens"], 2)

    def test_tps_after_records(self):
        m = StreamMonitor()
        m.record("a")
        m.record("b")
        self.assertGreaterEqual(m.tokens_per_second(), 0.0)


class TestLatencyPercentiles(unittest.TestCase):
    def test_empty(self):
        p = StreamMonitor().latency_percentiles()
        self.assertEqual(p["p50"], 0.0)
        self.assertEqual(p["p90"], 0.0)

    def test_single_interval(self):
        m = StreamMonitor()
        m.record("a")
        m.record("b")
        self.assertGreaterEqual(m.latency_percentiles()["p50"], 0.0)

    def test_multiple_intervals(self):
        m = StreamMonitor()
        for i in range(10):
            m.record(f"t{i}")
        p = m.latency_percentiles()
        self.assertGreaterEqual(p["p99"], p["p50"])


class TestStallDetection(unittest.TestCase):
    def test_no_stall_initially(self):
        self.assertFalse(StreamMonitor().detect_stall())

    def test_no_stall_recent_token(self):
        m = StreamMonitor()
        m.record("x")
        self.assertFalse(m.detect_stall(threshold_seconds=5.0))

    def test_stall_detected(self):
        m = StreamMonitor()
        m.record("x")
        with patch("lidco.streaming.stream_monitor.time.monotonic", return_value=time.monotonic() + 10):
            self.assertTrue(m.detect_stall(threshold_seconds=5.0))


class TestAnomalyDetection(unittest.TestCase):
    def test_no_anomalies_initial(self):
        self.assertEqual(StreamMonitor().alert_anomalies(), [])

    def test_throughput_drop(self):
        m = StreamMonitor()
        # Force known timing: 1 token over 2 seconds = 0.5 tps
        base_time = 1000.0
        with patch("lidco.streaming.stream_monitor.time.monotonic", side_effect=[base_time, base_time + 2.0, base_time + 2.0]):
            m.record("a")
        alerts = m.alert_anomalies(baseline_tps=100.0)
        self.assertTrue(any("drop" in a.lower() for a in alerts))

    def test_stall_alert(self):
        m = StreamMonitor()
        m.record("x")
        with patch("lidco.streaming.stream_monitor.time.monotonic", return_value=time.monotonic() + 10):
            alerts = m.alert_anomalies()
            self.assertTrue(any("stall" in a.lower() for a in alerts))


class TestReset(unittest.TestCase):
    def test_reset_clears_all(self):
        m = StreamMonitor()
        m.record("a")
        m.reset()
        self.assertEqual(m.stats()["total_tokens"], 0)


class TestMonitorStats(unittest.TestCase):
    def test_stats_keys(self):
        s = StreamMonitor().stats()
        for key in ("tps", "total_tokens", "duration", "stall_detected"):
            self.assertIn(key, s)


if __name__ == "__main__":
    unittest.main()
