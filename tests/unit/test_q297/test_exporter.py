"""Tests for MetricsExporter."""
from __future__ import annotations

import unittest

from lidco.observability.exporter import MetricsExporter, MetricPoint


class TestMetricPoint(unittest.TestCase):
    def test_fields(self):
        pt = MetricPoint(name="cpu", value=0.75, labels={"host": "a"}, timestamp=1.0)
        self.assertEqual(pt.name, "cpu")
        self.assertEqual(pt.value, 0.75)
        self.assertEqual(pt.labels, {"host": "a"})


class TestMetricsExporter(unittest.TestCase):
    def setUp(self):
        self.exp = MetricsExporter()

    def test_record_adds_point(self):
        self.exp.record("cpu", 0.5, {"host": "a"})
        self.assertEqual(len(self.exp._points), 1)
        self.assertEqual(self.exp._points[0].name, "cpu")

    def test_record_without_labels(self):
        self.exp.record("mem", 42.0)
        self.assertEqual(self.exp._points[0].labels, {})

    def test_counter_increments(self):
        self.assertEqual(self.exp.counter("req"), 1)
        self.assertEqual(self.exp.counter("req"), 2)
        self.assertEqual(self.exp.counter("req"), 3)

    def test_histogram_collects(self):
        self.exp.histogram("latency", 10.0)
        self.exp.histogram("latency", 20.0)
        self.assertEqual(len(self.exp._histograms["latency"]), 2)

    def test_export_prometheus_counters(self):
        self.exp.counter("requests")
        out = self.exp.export_prometheus()
        self.assertIn("# TYPE requests counter", out)
        self.assertIn("requests 1", out)

    def test_export_prometheus_histogram(self):
        self.exp.histogram("lat", 5.0)
        self.exp.histogram("lat", 15.0)
        out = self.exp.export_prometheus()
        self.assertIn("lat_count 2", out)
        self.assertIn("lat_sum 20.0", out)

    def test_export_prometheus_labels(self):
        self.exp.record("cpu", 0.8, {"host": "web1"})
        out = self.exp.export_prometheus()
        self.assertIn('host="web1"', out)

    def test_export_json(self):
        self.exp.counter("a")
        self.exp.histogram("b", 3.0)
        self.exp.record("c", 7.0)
        j = self.exp.export_json()
        self.assertEqual(j["counters"]["a"], 1)
        self.assertEqual(j["histograms"]["b"]["count"], 1)
        self.assertEqual(len(j["points"]), 1)

    def test_export_json_histogram_stats(self):
        self.exp.histogram("x", 2.0)
        self.exp.histogram("x", 8.0)
        h = self.exp.export_json()["histograms"]["x"]
        self.assertEqual(h["min"], 2.0)
        self.assertEqual(h["max"], 8.0)
        self.assertEqual(h["sum"], 10.0)

    def test_summary(self):
        self.exp.counter("r")
        self.exp.histogram("h", 1.0)
        self.exp.record("p", 2.0)
        s = self.exp.summary()
        self.assertEqual(s["total_points"], 1)
        self.assertEqual(s["counters"], 1)
        self.assertEqual(s["histograms"], 1)
        self.assertIn("r", s["counter_names"])
        self.assertIn("h", s["histogram_names"])


if __name__ == "__main__":
    unittest.main()
