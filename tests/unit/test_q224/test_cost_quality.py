"""Tests for lidco.routing.cost_quality."""
from __future__ import annotations

import unittest

from lidco.routing.cost_quality import CostQualityOptimizer, ModelProfile


def _profile(model: str, quality: float, cost: float, latency: float = 100.0) -> ModelProfile:
    return ModelProfile(model=model, avg_quality=quality, avg_cost_per_token=cost, avg_latency_ms=latency)


class TestCostQualityOptimizer(unittest.TestCase):
    def setUp(self) -> None:
        self.opt = CostQualityOptimizer()

    def test_empty_profiles(self) -> None:
        self.assertEqual(self.opt.profiles, [])
        self.assertEqual(self.opt.summary()["count"], 0)

    def test_add_profile(self) -> None:
        self.opt.add_profile(_profile("m", 0.8, 0.01))
        self.assertEqual(len(self.opt.profiles), 1)

    def test_optimize_no_constraints(self) -> None:
        self.opt.add_profile(_profile("a", 0.9, 0.05))
        self.opt.add_profile(_profile("b", 0.7, 0.01))
        result = self.opt.optimize()
        self.assertTrue(len(result) >= 1)

    def test_optimize_min_quality_filter(self) -> None:
        self.opt.add_profile(_profile("a", 0.9, 0.05))
        self.opt.add_profile(_profile("b", 0.3, 0.01))
        result = self.opt.optimize(min_quality=0.5)
        models = [p.model for p in result]
        self.assertIn("a", models)
        self.assertNotIn("b", models)

    def test_optimize_max_cost_filter(self) -> None:
        self.opt.add_profile(_profile("a", 0.9, 0.10))
        self.opt.add_profile(_profile("b", 0.7, 0.01))
        result = self.opt.optimize(max_cost=0.05)
        models = [p.model for p in result]
        self.assertNotIn("a", models)
        self.assertIn("b", models)

    def test_recommend_best_quality(self) -> None:
        self.opt.add_profile(_profile("a", 0.9, 0.05))
        self.opt.add_profile(_profile("b", 0.7, 0.01))
        rec = self.opt.recommend(min_quality=0.5)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.model, "a")

    def test_recommend_none_when_no_match(self) -> None:
        self.opt.add_profile(_profile("a", 0.3, 0.05))
        rec = self.opt.recommend(min_quality=0.9)
        self.assertIsNone(rec)

    def test_pareto_front_dominated_removed(self) -> None:
        # a dominates c (higher quality, lower cost)
        self.opt.add_profile(_profile("a", 0.9, 0.01))
        self.opt.add_profile(_profile("b", 0.5, 0.005))
        self.opt.add_profile(_profile("c", 0.8, 0.02))  # dominated by a
        front = self.opt.pareto_front()
        models = [p.model for p in front]
        self.assertIn("a", models)
        self.assertIn("b", models)
        self.assertNotIn("c", models)

    def test_summary(self) -> None:
        self.opt.add_profile(_profile("a", 0.9, 0.01, 50.0))
        s = self.opt.summary()
        self.assertEqual(s["count"], 1)
        self.assertEqual(s["profiles"][0]["model"], "a")

    def test_profiles_returns_copy(self) -> None:
        self.opt.add_profile(_profile("a", 0.9, 0.01))
        profiles = self.opt.profiles
        profiles.append(_profile("b", 0.5, 0.1))
        self.assertEqual(len(self.opt.profiles), 1)


if __name__ == "__main__":
    unittest.main()
