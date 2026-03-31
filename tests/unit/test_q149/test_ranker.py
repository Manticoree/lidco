"""Tests for CompletionRanker."""
from __future__ import annotations
import unittest
from lidco.completion.ranker import CompletionRanker, RankedItem


class TestRankedItem(unittest.TestCase):
    def test_defaults(self):
        item = RankedItem(text="foo", score=0.5)
        self.assertEqual(item.factors, {})

    def test_with_factors(self):
        item = RankedItem(text="bar", score=0.9, factors={"prefix": 1.0})
        self.assertEqual(item.factors["prefix"], 1.0)


class TestCompletionRanker(unittest.TestCase):
    def setUp(self):
        self.ranker = CompletionRanker()

    # --- prefix_score ---

    def test_prefix_exact_match(self):
        score = self.ranker._prefix_score("hello", "hello")
        self.assertEqual(score, 1.0)

    def test_prefix_partial_match(self):
        score = self.ranker._prefix_score("hello", "hel")
        self.assertEqual(score, 0.8)

    def test_prefix_no_match(self):
        score = self.ranker._prefix_score("hello", "xyz")
        self.assertEqual(score, 0.0)

    def test_prefix_empty_query(self):
        score = self.ranker._prefix_score("hello", "")
        self.assertEqual(score, 0.0)

    def test_prefix_case_insensitive(self):
        score = self.ranker._prefix_score("Hello", "hello")
        self.assertEqual(score, 1.0)

    # --- similarity_score ---

    def test_similarity_identical(self):
        score = self.ranker._similarity_score("test", "test")
        self.assertEqual(score, 1.0)

    def test_similarity_partial(self):
        score = self.ranker._similarity_score("testing", "test")
        self.assertGreater(score, 0.5)

    def test_similarity_no_overlap(self):
        score = self.ranker._similarity_score("abc", "xyz")
        self.assertLess(score, 0.3)

    def test_similarity_empty_query(self):
        score = self.ranker._similarity_score("abc", "")
        self.assertEqual(score, 0.0)

    # --- frequency_score ---

    def test_frequency_high_count(self):
        score = self.ranker._frequency_score("cmd", {"cmd": 50})
        self.assertGreater(score, 0.5)

    def test_frequency_zero_count(self):
        score = self.ranker._frequency_score("cmd", {"cmd": 0})
        self.assertEqual(score, 0.0)

    def test_frequency_missing(self):
        score = self.ranker._frequency_score("cmd", {})
        self.assertEqual(score, 0.0)

    def test_frequency_capped_at_one(self):
        score = self.ranker._frequency_score("cmd", {"cmd": 999999})
        self.assertLessEqual(score, 1.0)

    # --- recency_score ---

    def test_recency_normalized(self):
        score = self.ranker._recency_score("cmd", {"cmd": 0.8})
        self.assertEqual(score, 0.8)

    def test_recency_zero(self):
        score = self.ranker._recency_score("cmd", {"cmd": 0.0})
        self.assertEqual(score, 0.0)

    def test_recency_missing(self):
        score = self.ranker._recency_score("cmd", {})
        self.assertEqual(score, 0.0)

    # --- rank ---

    def test_rank_returns_sorted(self):
        items = ["apple", "app", "banana"]
        ranked = self.ranker.rank(items, "app")
        self.assertEqual(ranked[0].text, "app")

    def test_rank_with_usage(self):
        items = ["apple", "app"]
        ranked = self.ranker.rank(items, "ap", usage_counts={"apple": 100, "app": 0})
        # apple should rank higher due to frequency
        apple_score = next(r for r in ranked if r.text == "apple").score
        app_score = next(r for r in ranked if r.text == "app").score
        self.assertGreater(apple_score, app_score)

    def test_rank_empty_items(self):
        self.assertEqual(self.ranker.rank([], "q"), [])

    def test_rank_factors_present(self):
        ranked = self.ranker.rank(["foo"], "foo")
        self.assertIn("prefix", ranked[0].factors)
        self.assertIn("similarity", ranked[0].factors)

    # --- top ---

    def test_top_limits_results(self):
        items = [f"item{i}" for i in range(20)]
        top = self.ranker.top(items, "item", n=3)
        self.assertEqual(len(top), 3)

    def test_top_with_kwargs(self):
        items = ["abc", "abd"]
        top = self.ranker.top(items, "ab", n=1, usage_counts={"abc": 10})
        self.assertEqual(len(top), 1)


if __name__ == "__main__":
    unittest.main()
