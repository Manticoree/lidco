"""Tests for lidco.prompts.optimizer (Q246)."""
from __future__ import annotations

import unittest

from lidco.prompts.optimizer import PromptOptimizer, PromptVariant


class TestPromptOptimizerAddVariant(unittest.TestCase):
    def test_add_returns_id(self):
        opt = PromptOptimizer()
        vid = opt.add_variant("Hello world")
        self.assertIsInstance(vid, str)
        self.assertEqual(len(vid), 8)

    def test_add_multiple_unique_ids(self):
        opt = PromptOptimizer()
        ids = {opt.add_variant(f"prompt {i}") for i in range(10)}
        self.assertEqual(len(ids), 10)

    def test_list_after_add(self):
        opt = PromptOptimizer()
        opt.add_variant("p1")
        opt.add_variant("p2")
        self.assertEqual(len(opt.list_variants()), 2)

    def test_variant_stores_prompt(self):
        opt = PromptOptimizer()
        vid = opt.add_variant("test prompt")
        variants = opt.list_variants()
        self.assertEqual(variants[0].prompt, "test prompt")
        self.assertEqual(variants[0].id, vid)


class TestPromptOptimizerScore(unittest.TestCase):
    def test_record_score_updates_average(self):
        opt = PromptOptimizer()
        vid = opt.add_variant("p")
        opt.record_score(vid, 1.0)
        opt.record_score(vid, 3.0)
        v = opt.list_variants()[0]
        self.assertAlmostEqual(v.score, 2.0)
        self.assertEqual(v.uses, 2)

    def test_record_score_unknown_id_no_error(self):
        opt = PromptOptimizer()
        opt.record_score("nonexistent", 5.0)  # should not raise

    def test_single_score(self):
        opt = PromptOptimizer()
        vid = opt.add_variant("p")
        opt.record_score(vid, 4.5)
        self.assertAlmostEqual(opt.list_variants()[0].score, 4.5)


class TestPromptOptimizerBest(unittest.TestCase):
    def test_best_empty(self):
        opt = PromptOptimizer()
        self.assertIsNone(opt.best())

    def test_best_no_scores(self):
        opt = PromptOptimizer()
        opt.add_variant("p")
        self.assertIsNone(opt.best())

    def test_best_returns_highest(self):
        opt = PromptOptimizer()
        v1 = opt.add_variant("low")
        v2 = opt.add_variant("high")
        opt.record_score(v1, 1.0)
        opt.record_score(v2, 9.0)
        best = opt.best()
        self.assertIsNotNone(best)
        self.assertEqual(best.id, v2)


class TestPromptOptimizerSelect(unittest.TestCase):
    def test_select_empty(self):
        opt = PromptOptimizer()
        self.assertIsNone(opt.select())

    def test_select_unscored_returns_any(self):
        opt = PromptOptimizer()
        opt.add_variant("p")
        result = opt.select()
        self.assertIsNotNone(result)

    def test_select_scored_returns_variant(self):
        opt = PromptOptimizer()
        vid = opt.add_variant("p")
        opt.record_score(vid, 5.0)
        result = opt.select()
        self.assertEqual(result.id, vid)


class TestPromptOptimizerRemove(unittest.TestCase):
    def test_remove_existing(self):
        opt = PromptOptimizer()
        vid = opt.add_variant("p")
        self.assertTrue(opt.remove_variant(vid))
        self.assertEqual(len(opt.list_variants()), 0)

    def test_remove_nonexistent(self):
        opt = PromptOptimizer()
        self.assertFalse(opt.remove_variant("nope"))


class TestPromptOptimizerStats(unittest.TestCase):
    def test_stats_empty(self):
        opt = PromptOptimizer()
        s = opt.stats()
        self.assertEqual(s["total_variants"], 0)
        self.assertEqual(s["scored_variants"], 0)

    def test_stats_with_data(self):
        opt = PromptOptimizer()
        v1 = opt.add_variant("a")
        opt.add_variant("b")
        opt.record_score(v1, 3.0)
        s = opt.stats()
        self.assertEqual(s["total_variants"], 2)
        self.assertEqual(s["scored_variants"], 1)
        self.assertAlmostEqual(s["best_score"], 3.0)
        self.assertEqual(s["total_uses"], 1)


if __name__ == "__main__":
    unittest.main()
