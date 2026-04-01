"""Tests for context.priority_scorer — ScoredEntry, PriorityScorer."""
from __future__ import annotations

import time
import unittest

from lidco.context.priority_scorer import PriorityScorer, ScoredEntry


class TestScoredEntry(unittest.TestCase):
    def test_frozen(self):
        e = ScoredEntry(content="hi")
        with self.assertRaises(AttributeError):
            e.score = 1.0  # type: ignore[misc]

    def test_defaults(self):
        e = ScoredEntry(content="hi")
        self.assertEqual(e.score, 0.0)
        self.assertEqual(e.recency, 0.0)
        self.assertEqual(e.relevance, 0.0)
        self.assertEqual(e.references, 0)
        self.assertFalse(e.pinned)

    def test_equality(self):
        a = ScoredEntry(content="x", score=0.5)
        b = ScoredEntry(content="x", score=0.5)
        self.assertEqual(a, b)


class TestPriorityScorer(unittest.TestCase):
    def test_pinned_always_one(self):
        scorer = PriorityScorer()
        entry = scorer.score("important", pinned=True)
        self.assertEqual(entry.score, 1.0)
        self.assertTrue(entry.pinned)

    def test_recent_scores_higher(self):
        scorer = PriorityScorer(decay_rate=0.1)
        recent = scorer.score("data", timestamp=time.time(), references=0)
        old = scorer.score("data", timestamp=time.time() - 100, references=0)
        self.assertGreater(recent.score, old.score)

    def test_references_bonus(self):
        scorer = PriorityScorer()
        no_refs = scorer.score("data", timestamp=time.time())
        with_refs = scorer.score("data", timestamp=time.time(), references=5)
        self.assertGreater(with_refs.score, no_refs.score)

    def test_rank_descending(self):
        scorer = PriorityScorer()
        a = ScoredEntry(content="a", score=0.3)
        b = ScoredEntry(content="b", score=0.9)
        c = ScoredEntry(content="c", score=0.6)
        ranked = scorer.rank([a, b, c])
        self.assertEqual([e.content for e in ranked], ["b", "c", "a"])

    def test_decay_reduces_score(self):
        scorer = PriorityScorer(decay_rate=0.1)
        entry = ScoredEntry(content="x", score=0.8, recency=0.8)
        decayed = scorer.decay(entry, elapsed=10.0)
        self.assertLess(decayed.score, entry.score)

    def test_decay_pinned_unchanged(self):
        scorer = PriorityScorer()
        entry = ScoredEntry(content="x", score=1.0, pinned=True)
        decayed = scorer.decay(entry, elapsed=100.0)
        self.assertEqual(decayed.score, 1.0)

    def test_filter_by_budget_limits(self):
        scorer = PriorityScorer()
        # Each "xxxx" = 1 token
        entries = [
            ScoredEntry(content="a" * 40, score=0.9),  # 10 tokens
            ScoredEntry(content="b" * 40, score=0.8),  # 10 tokens
            ScoredEntry(content="c" * 40, score=0.7),  # 10 tokens
        ]
        result = scorer.filter_by_budget(entries, budget=20)
        self.assertEqual(len(result), 2)

    def test_filter_by_budget_empty(self):
        scorer = PriorityScorer()
        result = scorer.filter_by_budget([], budget=100)
        self.assertEqual(result, [])

    def test_score_zero_timestamp(self):
        scorer = PriorityScorer()
        entry = scorer.score("hello world", timestamp=0.0)
        self.assertGreater(entry.score, 0.0)

    def test_relevance_long_content(self):
        scorer = PriorityScorer()
        short = scorer.score("hi", timestamp=time.time())
        long = scorer.score("x" * 3000, timestamp=time.time())
        self.assertGreater(long.relevance, short.relevance)


if __name__ == "__main__":
    unittest.main()
