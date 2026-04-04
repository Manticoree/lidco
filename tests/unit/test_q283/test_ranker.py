"""Tests for lidco.adaptive.ranker — ContextRanker."""
from __future__ import annotations

import time
import unittest

from lidco.adaptive.ranker import ContextRanker, ContextItem


class TestContextRanker(unittest.TestCase):
    def setUp(self):
        self.ranker = ContextRanker()

    def test_add_and_items(self):
        item = ContextItem(text="hello world")
        self.ranker.add_item(item)
        self.assertEqual(len(self.ranker.items()), 1)
        self.assertEqual(self.ranker.items()[0].text, "hello world")

    def test_clear(self):
        self.ranker.add_item(ContextItem(text="a"))
        self.ranker.clear()
        self.assertEqual(len(self.ranker.items()), 0)

    def test_score_item_similarity(self):
        item = ContextItem(text="python sorting algorithm")
        score = self.ranker.score_item(item, "python sort")
        self.assertGreater(score, 0.0)

    def test_score_item_no_overlap(self):
        item = ContextItem(text="apples oranges bananas")
        score = self.ranker.score_item(item, "python code")
        # Only recency component, similarity should be 0
        self.assertGreaterEqual(score, 0.0)

    def test_score_item_exact_match(self):
        item = ContextItem(text="python")
        score = self.ranker.score_item(item, "python")
        # Perfect overlap + recency
        self.assertGreater(score, 0.5)

    def test_rank_order(self):
        now = time.time()
        items = [
            ContextItem(text="unrelated stuff about cooking", timestamp=now),
            ContextItem(text="python sorting algorithms are fast", timestamp=now),
            ContextItem(text="python list sort method", timestamp=now),
        ]
        ranked = self.ranker.rank(items, "python sort")
        # Items with "python" and "sort" should rank higher
        self.assertIn("python", ranked[0].text)

    def test_rank_empty(self):
        ranked = self.ranker.rank([], "query")
        self.assertEqual(ranked, [])

    def test_weight_affects_score(self):
        item_low = ContextItem(text="python code", weight=0.1)
        item_high = ContextItem(text="python code", weight=2.0)
        score_low = self.ranker.score_item(item_low, "python")
        score_high = self.ranker.score_item(item_high, "python")
        self.assertGreater(score_high, score_low)

    def test_recency_decay(self):
        recent = ContextItem(text="test", timestamp=time.time())
        old = ContextItem(text="test", timestamp=time.time() - 3600)
        score_recent = self.ranker.score_item(recent, "test")
        score_old = self.ranker.score_item(old, "test")
        self.assertGreater(score_recent, score_old)

    def test_custom_weights(self):
        ranker = ContextRanker(recency_weight=0.0, similarity_weight=1.0)
        item = ContextItem(text="python", timestamp=time.time() - 7200)
        score = ranker.score_item(item, "python")
        # Should be pure similarity, no recency
        self.assertGreater(score, 0.0)


if __name__ == "__main__":
    unittest.main()
