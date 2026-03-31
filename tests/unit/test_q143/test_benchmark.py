"""Tests for PerfBenchmark — Task 849."""

from __future__ import annotations

import unittest

from lidco.diagnostics.benchmark import PerfBenchmark, BenchmarkResult


class TestBenchmarkResult(unittest.TestCase):
    def test_dataclass_fields(self):
        r = BenchmarkResult("t", 10, 1.0, 0.1, 0.05, 0.2, 10.0)
        self.assertEqual(r.name, "t")
        self.assertEqual(r.iterations, 10)
        self.assertAlmostEqual(r.total_time, 1.0)
        self.assertAlmostEqual(r.avg_time, 0.1)
        self.assertAlmostEqual(r.min_time, 0.05)
        self.assertAlmostEqual(r.max_time, 0.2)
        self.assertAlmostEqual(r.ops_per_second, 10.0)


class TestPerfBenchmarkRun(unittest.TestCase):
    def test_basic_run(self):
        bench = PerfBenchmark()
        result = bench.run("noop", lambda: None, iterations=10)
        self.assertEqual(result.name, "noop")
        self.assertEqual(result.iterations, 10)
        self.assertGreater(result.total_time, 0)
        self.assertGreater(result.ops_per_second, 0)

    def test_min_leq_avg_leq_max(self):
        bench = PerfBenchmark()
        result = bench.run("noop", lambda: None, iterations=50)
        self.assertLessEqual(result.min_time, result.avg_time)
        self.assertLessEqual(result.avg_time, result.max_time)

    def test_total_is_sum_approx(self):
        bench = PerfBenchmark()
        result = bench.run("noop", lambda: None, iterations=20)
        self.assertAlmostEqual(result.total_time, result.avg_time * result.iterations, places=5)

    def test_result_added_to_history(self):
        bench = PerfBenchmark()
        bench.run("a", lambda: None, iterations=5)
        self.assertEqual(len(bench.history), 1)

    def test_default_iterations(self):
        bench = PerfBenchmark()
        result = bench.run("d", lambda: None)
        self.assertEqual(result.iterations, 100)

    def test_fn_actually_called(self):
        counter = {"n": 0}
        def inc():
            counter["n"] += 1
        bench = PerfBenchmark()
        bench.run("inc", inc, iterations=7)
        self.assertEqual(counter["n"], 7)


class TestPerfBenchmarkCompare(unittest.TestCase):
    def test_compare_returns_winner(self):
        bench = PerfBenchmark()
        result = bench.compare("fast", lambda: None, "slow", lambda: sum(range(100)), iterations=10)
        self.assertIn("winner", result)
        self.assertIn("speedup", result)
        self.assertIn("a", result)
        self.assertIn("b", result)

    def test_compare_speedup_positive(self):
        bench = PerfBenchmark()
        result = bench.compare("a", lambda: None, "b", lambda: None, iterations=10)
        self.assertGreater(result["speedup"], 0)

    def test_compare_adds_to_history(self):
        bench = PerfBenchmark()
        bench.compare("a", lambda: None, "b", lambda: None, iterations=5)
        self.assertEqual(len(bench.history), 2)

    def test_winner_is_one_of_names(self):
        bench = PerfBenchmark()
        result = bench.compare("x", lambda: None, "y", lambda: None, iterations=5)
        self.assertIn(result["winner"], ("x", "y"))


class TestPerfBenchmarkSuite(unittest.TestCase):
    def test_suite_runs_all(self):
        bench = PerfBenchmark()
        results = bench.suite({"a": lambda: None, "b": lambda: None}, iterations=5)
        self.assertEqual(len(results), 2)
        names = {r.name for r in results}
        self.assertEqual(names, {"a", "b"})

    def test_suite_appends_history(self):
        bench = PerfBenchmark()
        bench.suite({"a": lambda: None, "b": lambda: None, "c": lambda: None}, iterations=3)
        self.assertEqual(len(bench.history), 3)

    def test_suite_empty(self):
        bench = PerfBenchmark()
        results = bench.suite({}, iterations=5)
        self.assertEqual(results, [])


class TestFormatResult(unittest.TestCase):
    def test_format_contains_name(self):
        r = BenchmarkResult("mytest", 100, 0.5, 0.005, 0.001, 0.01, 200.0)
        text = PerfBenchmark.format_result(r)
        self.assertIn("mytest", text)

    def test_format_contains_ops(self):
        r = BenchmarkResult("t", 10, 0.1, 0.01, 0.005, 0.02, 100.0)
        text = PerfBenchmark.format_result(r)
        self.assertIn("ops/s", text)

    def test_format_contains_ms(self):
        r = BenchmarkResult("t", 10, 0.1, 0.01, 0.005, 0.02, 100.0)
        text = PerfBenchmark.format_result(r)
        self.assertIn("ms", text)


class TestHistory(unittest.TestCase):
    def test_history_empty_initially(self):
        bench = PerfBenchmark()
        self.assertEqual(bench.history, [])

    def test_history_is_copy(self):
        bench = PerfBenchmark()
        bench.run("a", lambda: None, iterations=3)
        h = bench.history
        h.clear()
        self.assertEqual(len(bench.history), 1)


if __name__ == "__main__":
    unittest.main()
