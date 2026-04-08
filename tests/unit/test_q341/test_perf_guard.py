"""Tests for PerformanceRegressionGuard (Q341 Task 4)."""
from __future__ import annotations

import unittest


class TestTrackAndFlagSlow(unittest.TestCase):
    def setUp(self):
        from lidco.stability.perf_guard import PerformanceRegressionGuard
        self.g = PerformanceRegressionGuard(slow_threshold=5.0)

    def test_no_times_returns_empty(self):
        self.g.track_times({})
        self.assertEqual(self.g.flag_slow_tests(), [])

    def test_fast_tests_not_flagged(self):
        self.g.track_times({"test_fast": 1.0, "test_ok": 4.9})
        self.assertEqual(self.g.flag_slow_tests(), [])

    def test_slow_test_flagged(self):
        self.g.track_times({"test_slow": 10.0})
        result = self.g.flag_slow_tests()
        self.assertTrue(any(r["test_name"] == "test_slow" for r in result))

    def test_over_by_calculated_correctly(self):
        self.g.track_times({"test_slow": 8.0})
        result = self.g.flag_slow_tests()
        item = next(r for r in result if r["test_name"] == "test_slow")
        self.assertAlmostEqual(item["over_by"], 3.0, places=3)

    def test_threshold_and_duration_in_result(self):
        self.g.track_times({"test_x": 7.5})
        result = self.g.flag_slow_tests()
        item = next(r for r in result if r["test_name"] == "test_x")
        self.assertEqual(item["threshold"], 5.0)
        self.assertEqual(item["duration"], 7.5)

    def test_results_sorted_by_duration_descending(self):
        self.g.track_times({"a": 9.0, "b": 6.0, "c": 12.0})
        result = self.g.flag_slow_tests()
        durations = [r["duration"] for r in result]
        self.assertEqual(durations, sorted(durations, reverse=True))

    def test_custom_threshold(self):
        from lidco.stability.perf_guard import PerformanceRegressionGuard
        g = PerformanceRegressionGuard(slow_threshold=1.0)
        g.track_times({"test_x": 1.5})
        result = g.flag_slow_tests()
        self.assertTrue(any(r["test_name"] == "test_x" for r in result))


class TestDetectRegressions(unittest.TestCase):
    def setUp(self):
        from lidco.stability.perf_guard import PerformanceRegressionGuard
        self.g = PerformanceRegressionGuard()

    def test_no_regression_returns_empty(self):
        prev = {"test_a": 1.0}
        curr = {"test_a": 1.2}
        self.assertEqual(self.g.detect_regressions(prev, curr), [])

    def test_regression_over_50_percent_detected(self):
        prev = {"test_a": 2.0}
        curr = {"test_a": 4.0}
        result = self.g.detect_regressions(prev, curr)
        self.assertTrue(any(r["test_name"] == "test_a" for r in result))

    def test_increase_pct_calculated_correctly(self):
        prev = {"test_b": 2.0}
        curr = {"test_b": 3.0}
        result = self.g.detect_regressions(prev, curr)
        item = next((r for r in result if r["test_name"] == "test_b"), None)
        self.assertIsNone(item)  # 50% exactly, not > 50%

    def test_new_test_without_previous_skipped(self):
        prev = {}
        curr = {"test_new": 10.0}
        result = self.g.detect_regressions(prev, curr)
        self.assertEqual(result, [])

    def test_previous_and_current_in_result(self):
        prev = {"slow_test": 1.0}
        curr = {"slow_test": 5.0}
        result = self.g.detect_regressions(prev, curr)
        item = next(r for r in result if r["test_name"] == "slow_test")
        self.assertEqual(item["previous"], 1.0)
        self.assertEqual(item["current"], 5.0)


class TestSuggestParallelization(unittest.TestCase):
    def setUp(self):
        from lidco.stability.perf_guard import PerformanceRegressionGuard
        self.g = PerformanceRegressionGuard()

    def test_empty_times_returns_empty_workers(self):
        result = self.g.suggest_parallelization({}, num_workers=4)
        self.assertEqual(len(result["workers"]), 4)
        self.assertEqual(result["estimated_time"], 0.0)

    def test_workers_count_matches_num_workers(self):
        times = {"a": 1.0, "b": 2.0}
        result = self.g.suggest_parallelization(times, num_workers=3)
        self.assertEqual(len(result["workers"]), 3)

    def test_all_tests_assigned(self):
        times = {"a": 1.0, "b": 2.0, "c": 3.0, "d": 1.5}
        result = self.g.suggest_parallelization(times, num_workers=2)
        all_assigned = [t for w in result["workers"] for t in w]
        self.assertEqual(sorted(all_assigned), sorted(times.keys()))

    def test_speedup_greater_than_one_with_multiple_workers(self):
        times = {"a": 5.0, "b": 5.0, "c": 5.0, "d": 5.0}
        result = self.g.suggest_parallelization(times, num_workers=4)
        self.assertGreater(result["speedup"], 1.0)

    def test_estimated_time_is_positive(self):
        times = {"a": 2.0, "b": 3.0}
        result = self.g.suggest_parallelization(times, num_workers=2)
        self.assertGreater(result["estimated_time"], 0.0)


if __name__ == "__main__":
    unittest.main()
