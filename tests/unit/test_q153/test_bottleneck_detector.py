"""Tests for BottleneckDetector."""
from __future__ import annotations

import unittest

from lidco.perf.timing_profiler import TimingRecord
from lidco.perf.bottleneck_detector import BottleneckDetector, Bottleneck


def _rec(name: str, elapsed: float) -> TimingRecord:
    return TimingRecord(name=name, elapsed=elapsed, started_at=0, ended_at=elapsed)


class TestBottleneckDataclass(unittest.TestCase):
    def test_fields(self):
        b = Bottleneck(name="op", avg_time=0.5, call_count=3, total_time=1.5, percentage=75.0, severity="high")
        self.assertEqual(b.name, "op")
        self.assertEqual(b.severity, "high")
        self.assertEqual(b.call_count, 3)


class TestAnalyze(unittest.TestCase):
    def test_empty_records(self):
        d = BottleneckDetector()
        self.assertEqual(d.analyze([]), [])

    def test_below_threshold_excluded(self):
        d = BottleneckDetector(threshold_ms=100)
        records = [_rec("fast", 0.01)]  # 10ms
        self.assertEqual(d.analyze(records), [])

    def test_above_threshold_included(self):
        d = BottleneckDetector(threshold_ms=100)
        records = [_rec("slow", 0.5)]  # 500ms
        result = d.analyze(records)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "slow")

    def test_severity_low(self):
        d = BottleneckDetector(threshold_ms=50)
        records = [_rec("op", 0.08)]  # 80ms
        result = d.analyze(records)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].severity, "low")

    def test_severity_medium(self):
        d = BottleneckDetector(threshold_ms=100)
        records = [_rec("op", 0.6)]  # 600ms
        result = d.analyze(records)
        self.assertEqual(result[0].severity, "medium")

    def test_severity_high(self):
        d = BottleneckDetector(threshold_ms=100)
        records = [_rec("op", 2.0)]  # 2000ms
        result = d.analyze(records)
        self.assertEqual(result[0].severity, "high")

    def test_grouped_by_name(self):
        d = BottleneckDetector(threshold_ms=50)
        records = [_rec("op", 0.1), _rec("op", 0.2), _rec("other", 0.3)]
        result = d.analyze(records)
        names = {b.name for b in result}
        self.assertIn("op", names)
        self.assertIn("other", names)

    def test_call_count(self):
        d = BottleneckDetector(threshold_ms=50)
        records = [_rec("op", 0.1)] * 5
        result = d.analyze(records)
        self.assertEqual(result[0].call_count, 5)

    def test_percentage_sums_to_100(self):
        d = BottleneckDetector(threshold_ms=0)
        records = [_rec("a", 0.5), _rec("b", 0.5)]
        result = d.analyze(records)
        total_pct = sum(b.percentage for b in result)
        self.assertAlmostEqual(total_pct, 100.0, places=1)

    def test_sorted_by_total_time(self):
        d = BottleneckDetector(threshold_ms=0)
        records = [_rec("small", 0.1), _rec("big", 1.0), _rec("mid", 0.5)]
        result = d.analyze(records)
        self.assertEqual(result[0].name, "big")


class TestTopBottlenecks(unittest.TestCase):
    def test_empty(self):
        d = BottleneckDetector()
        self.assertEqual(d.top_bottlenecks([]), [])

    def test_returns_n(self):
        d = BottleneckDetector()
        records = [_rec(f"op{i}", float(i) * 0.001) for i in range(10)]
        result = d.top_bottlenecks(records, n=3)
        self.assertEqual(len(result), 3)

    def test_top_sorted_by_total(self):
        d = BottleneckDetector()
        records = [_rec("a", 0.01), _rec("b", 1.0)]
        result = d.top_bottlenecks(records, n=2)
        self.assertEqual(result[0].name, "b")

    def test_threshold_not_applied(self):
        d = BottleneckDetector(threshold_ms=99999)
        records = [_rec("fast", 0.001)]
        result = d.top_bottlenecks(records)
        self.assertEqual(len(result), 1)


class TestFormatReport(unittest.TestCase):
    def test_empty(self):
        d = BottleneckDetector()
        self.assertIn("No bottlenecks", d.format_report([]))

    def test_contains_header(self):
        d = BottleneckDetector()
        bns = [Bottleneck(name="op", avg_time=0.1, call_count=2, total_time=0.2, percentage=50.0, severity="low")]
        report = d.format_report(bns)
        self.assertIn("Bottleneck Report", report)
        self.assertIn("op", report)

    def test_contains_severity(self):
        d = BottleneckDetector()
        bns = [Bottleneck(name="x", avg_time=1.0, call_count=1, total_time=1.0, percentage=100.0, severity="high")]
        report = d.format_report(bns)
        self.assertIn("high", report)


class TestSuggestOptimizations(unittest.TestCase):
    def test_empty(self):
        d = BottleneckDetector()
        self.assertEqual(d.suggest_optimizations([]), [])

    def test_high_severity_suggestion(self):
        d = BottleneckDetector()
        bns = [Bottleneck(name="op", avg_time=2.0, call_count=1, total_time=2.0, percentage=50.0, severity="high")]
        sugs = d.suggest_optimizations(bns)
        self.assertTrue(any("CRITICAL" in s for s in sugs))

    def test_high_call_count_suggestion(self):
        d = BottleneckDetector()
        bns = [Bottleneck(name="op", avg_time=0.1, call_count=20, total_time=2.0, percentage=50.0, severity="low")]
        sugs = d.suggest_optimizations(bns)
        self.assertTrue(any("batch" in s.lower() or "memoiz" in s.lower() for s in sugs))

    def test_io_suggestion(self):
        d = BottleneckDetector()
        bns = [Bottleneck(name="file_read", avg_time=0.1, call_count=1, total_time=0.1, percentage=10.0, severity="low")]
        sugs = d.suggest_optimizations(bns)
        self.assertTrue(any("I/O" in s for s in sugs))

    def test_db_suggestion(self):
        d = BottleneckDetector()
        bns = [Bottleneck(name="db_query", avg_time=0.1, call_count=1, total_time=0.1, percentage=10.0, severity="low")]
        sugs = d.suggest_optimizations(bns)
        self.assertTrue(any("database" in s.lower() for s in sugs))

    def test_dominant_percentage_suggestion(self):
        d = BottleneckDetector()
        bns = [Bottleneck(name="main", avg_time=0.1, call_count=1, total_time=0.1, percentage=80.0, severity="low")]
        sugs = d.suggest_optimizations(bns)
        self.assertTrue(any("80%" in s for s in sugs))

    def test_fallback_suggestion(self):
        d = BottleneckDetector()
        bns = [Bottleneck(name="misc", avg_time=0.05, call_count=1, total_time=0.05, percentage=5.0, severity="low")]
        sugs = d.suggest_optimizations(bns)
        self.assertTrue(len(sugs) > 0)


if __name__ == "__main__":
    unittest.main()
