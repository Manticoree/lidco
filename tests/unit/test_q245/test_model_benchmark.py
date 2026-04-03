"""Tests for ModelBenchmark (Q245)."""
from __future__ import annotations

import unittest

from lidco.llm.model_benchmark import BenchmarkResult, ModelBenchmark


def _result(model: str, latency: float = 100.0, quality: float = 0.9, cost: float = 0.01) -> BenchmarkResult:
    return BenchmarkResult(model=model, latency_ms=latency, quality_score=quality, cost_estimate=cost)


class TestBenchmarkResult(unittest.TestCase):
    def test_defaults(self):
        r = BenchmarkResult(model="m", latency_ms=10, quality_score=0.8, cost_estimate=0.01)
        self.assertEqual(r.rank, 0)

    def test_frozen(self):
        r = _result("m")
        with self.assertRaises(AttributeError):
            r.model = "x"  # type: ignore[misc]


class TestModelBenchmarkAddResult(unittest.TestCase):
    def test_add_result(self):
        bench = ModelBenchmark()
        bench.add_result(_result("a"))
        self.assertEqual(len(bench.ranking()), 1)

    def test_add_multiple(self):
        bench = ModelBenchmark()
        bench.add_result(_result("a"))
        bench.add_result(_result("b"))
        self.assertEqual(len(bench.ranking()), 2)


class TestModelBenchmarkRanking(unittest.TestCase):
    def test_ranking_by_quality_desc(self):
        bench = ModelBenchmark()
        bench.add_result(_result("low", quality=0.5))
        bench.add_result(_result("high", quality=0.9))
        ranked = bench.ranking()
        self.assertEqual(ranked[0].model, "high")
        self.assertEqual(ranked[1].model, "low")

    def test_ranking_tiebreak_latency(self):
        bench = ModelBenchmark()
        bench.add_result(_result("slow", latency=200, quality=0.9))
        bench.add_result(_result("fast", latency=50, quality=0.9))
        ranked = bench.ranking()
        self.assertEqual(ranked[0].model, "fast")

    def test_ranking_assigns_ranks(self):
        bench = ModelBenchmark()
        bench.add_result(_result("a"))
        bench.add_result(_result("b"))
        ranked = bench.ranking()
        self.assertEqual(ranked[0].rank, 1)
        self.assertEqual(ranked[1].rank, 2)

    def test_ranking_empty(self):
        bench = ModelBenchmark()
        self.assertEqual(bench.ranking(), [])


class TestModelBenchmarkCompare(unittest.TestCase):
    def test_compare_existing(self):
        bench = ModelBenchmark()
        bench.add_result(_result("a", latency=100, quality=0.9, cost=0.01))
        bench.add_result(_result("b", latency=200, quality=0.8, cost=0.02))
        cmp = bench.compare("a", "b")
        self.assertEqual(cmp["model_a"], "a")
        self.assertEqual(cmp["model_b"], "b")
        self.assertAlmostEqual(cmp["latency_diff_ms"], -100.0)
        self.assertAlmostEqual(cmp["quality_diff"], 0.1)
        self.assertEqual(cmp["winner"], "a")

    def test_compare_nonexistent(self):
        bench = ModelBenchmark()
        cmp = bench.compare("x", "y")
        self.assertEqual(cmp["winner"], "")

    def test_compare_one_missing(self):
        bench = ModelBenchmark()
        bench.add_result(_result("a"))
        cmp = bench.compare("a", "z")
        self.assertEqual(cmp["winner"], "a")


class TestModelBenchmarkSummary(unittest.TestCase):
    def test_summary_empty(self):
        bench = ModelBenchmark()
        self.assertEqual(bench.summary(), "No benchmark results.")

    def test_summary_has_content(self):
        bench = ModelBenchmark()
        bench.add_result(_result("gpt-4"))
        s = bench.summary()
        self.assertIn("gpt-4", s)
        self.assertIn("#1", s)


class TestModelBenchmarkBest(unittest.TestCase):
    def test_best_empty(self):
        bench = ModelBenchmark()
        self.assertIsNone(bench.best())

    def test_best_returns_top(self):
        bench = ModelBenchmark()
        bench.add_result(_result("a", quality=0.5))
        bench.add_result(_result("b", quality=0.9))
        best = bench.best()
        self.assertIsNotNone(best)
        self.assertEqual(best.model, "b")

    def test_best_rank_is_one(self):
        bench = ModelBenchmark()
        bench.add_result(_result("only"))
        self.assertEqual(bench.best().rank, 1)


if __name__ == "__main__":
    unittest.main()
