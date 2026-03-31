"""Tests for PerfReport."""
from __future__ import annotations

import unittest

from lidco.perf.timing_profiler import TimingRecord
from lidco.perf.perf_report import PerfReport, PerfSummary


def _rec(elapsed: float) -> TimingRecord:
    return TimingRecord(name="op", elapsed=elapsed, started_at=0, ended_at=elapsed)


class TestPerfSummary(unittest.TestCase):
    def test_fields(self):
        s = PerfSummary(total_operations=10, total_time=1.0, avg_time=0.1, p50=0.09, p90=0.15, p99=0.2)
        self.assertEqual(s.total_operations, 10)
        self.assertAlmostEqual(s.avg_time, 0.1)


class TestCompute(unittest.TestCase):
    def setUp(self):
        self.r = PerfReport()

    def test_empty_records(self):
        s = self.r.compute([])
        self.assertEqual(s.total_operations, 0)
        self.assertEqual(s.total_time, 0.0)
        self.assertEqual(s.p50, 0.0)

    def test_single_record(self):
        s = self.r.compute([_rec(0.5)])
        self.assertEqual(s.total_operations, 1)
        self.assertAlmostEqual(s.total_time, 0.5)
        self.assertAlmostEqual(s.avg_time, 0.5)
        self.assertAlmostEqual(s.p50, 0.5)

    def test_multiple_records(self):
        records = [_rec(0.1), _rec(0.2), _rec(0.3), _rec(0.4)]
        s = self.r.compute(records)
        self.assertEqual(s.total_operations, 4)
        self.assertAlmostEqual(s.total_time, 1.0)
        self.assertAlmostEqual(s.avg_time, 0.25)

    def test_p50_median(self):
        records = [_rec(float(i)) for i in range(1, 101)]
        s = self.r.compute(records)
        self.assertAlmostEqual(s.p50, 50.5, places=0)

    def test_p90(self):
        records = [_rec(float(i)) for i in range(1, 101)]
        s = self.r.compute(records)
        self.assertGreater(s.p90, s.p50)

    def test_p99_near_max(self):
        records = [_rec(float(i)) for i in range(1, 101)]
        s = self.r.compute(records)
        self.assertGreater(s.p99, s.p90)

    def test_percentile_ordering(self):
        records = [_rec(float(i) * 0.01) for i in range(100)]
        s = self.r.compute(records)
        self.assertLessEqual(s.p50, s.p90)
        self.assertLessEqual(s.p90, s.p99)


class TestCompare(unittest.TestCase):
    def setUp(self):
        self.r = PerfReport()

    def test_regression_detected(self):
        before = PerfSummary(10, 1.0, 0.1, 0.1, 0.1, 0.1)
        after = PerfSummary(10, 2.0, 0.2, 0.2, 0.2, 0.2)
        result = self.r.compare(before, after)
        self.assertEqual(result["avg_time"]["direction"], "regression")

    def test_improvement_detected(self):
        before = PerfSummary(10, 2.0, 0.2, 0.2, 0.2, 0.2)
        after = PerfSummary(10, 1.0, 0.1, 0.1, 0.1, 0.1)
        result = self.r.compare(before, after)
        self.assertEqual(result["avg_time"]["direction"], "improvement")

    def test_unchanged(self):
        s = PerfSummary(10, 1.0, 0.1, 0.1, 0.1, 0.1)
        result = self.r.compare(s, s)
        self.assertEqual(result["avg_time"]["direction"], "unchanged")

    def test_pct_change(self):
        before = PerfSummary(10, 1.0, 0.1, 0.1, 0.1, 0.1)
        after = PerfSummary(10, 1.5, 0.15, 0.15, 0.15, 0.15)
        result = self.r.compare(before, after)
        self.assertAlmostEqual(result["avg_time"]["pct_change"], 50.0)

    def test_before_zero_avg(self):
        before = PerfSummary(0, 0.0, 0.0, 0.0, 0.0, 0.0)
        after = PerfSummary(10, 1.0, 0.1, 0.1, 0.1, 0.1)
        result = self.r.compare(before, after)
        self.assertEqual(result["avg_time"]["pct_change"], 100.0)

    def test_total_operations_included(self):
        before = PerfSummary(5, 1.0, 0.2, 0.2, 0.2, 0.2)
        after = PerfSummary(10, 1.0, 0.1, 0.1, 0.1, 0.1)
        result = self.r.compare(before, after)
        self.assertEqual(result["total_operations"]["before"], 5)
        self.assertEqual(result["total_operations"]["after"], 10)


class TestFormatSummary(unittest.TestCase):
    def test_output_contains_fields(self):
        r = PerfReport()
        s = PerfSummary(10, 1.0, 0.1, 0.05, 0.15, 0.19)
        output = r.format_summary(s)
        self.assertIn("Performance Summary", output)
        self.assertIn("Operations: 10", output)
        self.assertIn("P50", output)
        self.assertIn("P90", output)
        self.assertIn("P99", output)

    def test_ms_units(self):
        r = PerfReport()
        s = PerfSummary(1, 0.001, 0.001, 0.001, 0.001, 0.001)
        output = r.format_summary(s)
        self.assertIn("ms", output)


class TestIsRegression(unittest.TestCase):
    def setUp(self):
        self.r = PerfReport()

    def test_regression_true(self):
        before = PerfSummary(10, 1.0, 0.1, 0.1, 0.1, 0.1)
        after = PerfSummary(10, 2.0, 0.2, 0.2, 0.2, 0.2)
        self.assertTrue(self.r.is_regression(before, after))

    def test_regression_false_slight_increase(self):
        before = PerfSummary(10, 1.0, 0.1, 0.1, 0.1, 0.1)
        after = PerfSummary(10, 1.05, 0.105, 0.105, 0.105, 0.105)
        self.assertFalse(self.r.is_regression(before, after))

    def test_regression_false_improvement(self):
        before = PerfSummary(10, 1.0, 0.1, 0.1, 0.1, 0.1)
        after = PerfSummary(10, 0.5, 0.05, 0.05, 0.05, 0.05)
        self.assertFalse(self.r.is_regression(before, after))

    def test_custom_threshold(self):
        before = PerfSummary(10, 1.0, 0.1, 0.1, 0.1, 0.1)
        after = PerfSummary(10, 1.06, 0.106, 0.106, 0.106, 0.106)
        self.assertTrue(self.r.is_regression(before, after, threshold=0.05))

    def test_before_zero(self):
        before = PerfSummary(0, 0.0, 0.0, 0.0, 0.0, 0.0)
        after = PerfSummary(1, 0.1, 0.1, 0.1, 0.1, 0.1)
        self.assertTrue(self.r.is_regression(before, after))


class TestTrend(unittest.TestCase):
    def setUp(self):
        self.r = PerfReport()

    def test_single_summary_stable(self):
        s = PerfSummary(10, 1.0, 0.1, 0.1, 0.1, 0.1)
        self.assertEqual(self.r.trend([s]), "stable")

    def test_degrading(self):
        summaries = [PerfSummary(10, 1.0, 0.1, 0.1, 0.1, 0.1) for _ in range(3)]
        summaries += [PerfSummary(10, 2.0, 0.5, 0.5, 0.5, 0.5) for _ in range(3)]
        self.assertEqual(self.r.trend(summaries), "degrading")

    def test_improving(self):
        summaries = [PerfSummary(10, 2.0, 0.5, 0.5, 0.5, 0.5) for _ in range(3)]
        summaries += [PerfSummary(10, 1.0, 0.1, 0.1, 0.1, 0.1) for _ in range(3)]
        self.assertEqual(self.r.trend(summaries), "improving")

    def test_stable(self):
        summaries = [PerfSummary(10, 1.0, 0.1, 0.1, 0.1, 0.1) for _ in range(6)]
        self.assertEqual(self.r.trend(summaries), "stable")

    def test_empty_stable(self):
        self.assertEqual(self.r.trend([]), "stable")


if __name__ == "__main__":
    unittest.main()
