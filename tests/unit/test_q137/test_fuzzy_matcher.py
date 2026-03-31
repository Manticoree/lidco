"""Tests for Q137 FuzzyMatcher."""
from __future__ import annotations
import unittest
from lidco.text.fuzzy_matcher import FuzzyMatcher, MatchResult


class TestMatchResult(unittest.TestCase):
    def test_dataclass_fields(self):
        r = MatchResult(candidate="foo", score=0.8, index=0)
        self.assertEqual(r.candidate, "foo")
        self.assertEqual(r.score, 0.8)
        self.assertEqual(r.index, 0)

    def test_equality(self):
        a = MatchResult("a", 0.5, 0)
        b = MatchResult("a", 0.5, 0)
        self.assertEqual(a, b)


class TestFuzzyMatcher(unittest.TestCase):
    def setUp(self):
        self.candidates = ["apple", "application", "banana", "band", "apply"]
        self.matcher = FuzzyMatcher(self.candidates)

    def test_candidates_property(self):
        self.assertEqual(self.matcher.candidates, self.candidates)

    def test_candidates_property_returns_copy(self):
        c = self.matcher.candidates
        c.append("extra")
        self.assertNotIn("extra", self.matcher.candidates)

    def test_match_returns_list(self):
        results = self.matcher.match("apple")
        self.assertIsInstance(results, list)

    def test_match_exact(self):
        results = self.matcher.match("apple")
        self.assertTrue(any(r.candidate == "apple" for r in results))

    def test_match_score_is_1_for_exact(self):
        results = self.matcher.match("apple")
        exact = [r for r in results if r.candidate == "apple"]
        self.assertEqual(len(exact), 1)
        self.assertAlmostEqual(exact[0].score, 1.0)

    def test_match_sorted_by_score_desc(self):
        results = self.matcher.match("appl", threshold=0.3)
        scores = [r.score for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_match_threshold_filters(self):
        results = self.matcher.match("apple", threshold=0.9)
        for r in results:
            self.assertGreaterEqual(r.score, 0.9)

    def test_match_high_threshold_empty(self):
        results = self.matcher.match("xyz", threshold=0.99)
        self.assertEqual(results, [])

    def test_match_low_threshold_includes_more(self):
        low = self.matcher.match("app", threshold=0.2)
        high = self.matcher.match("app", threshold=0.8)
        self.assertGreaterEqual(len(low), len(high))

    def test_match_index_correct(self):
        results = self.matcher.match("banana")
        exact = [r for r in results if r.candidate == "banana"]
        self.assertEqual(exact[0].index, 2)

    def test_best_match_returns_result(self):
        result = self.matcher.best_match("apple")
        self.assertIsNotNone(result)
        self.assertEqual(result.candidate, "apple")

    def test_best_match_empty_candidates(self):
        m = FuzzyMatcher([])
        self.assertIsNone(m.best_match("test"))

    def test_best_match_picks_highest(self):
        result = self.matcher.best_match("appl")
        self.assertIsNotNone(result)
        # "apple" or "apply" should score highest
        self.assertIn(result.candidate, ["apple", "apply"])

    def test_match_all_returns_all(self):
        results = self.matcher.match_all("test")
        self.assertEqual(len(results), len(self.candidates))

    def test_match_all_sorted_by_score_desc(self):
        results = self.matcher.match_all("app")
        scores = [r.score for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_match_all_includes_zero_scores(self):
        m = FuzzyMatcher(["aaa", "zzz"])
        results = m.match_all("aaa")
        self.assertEqual(len(results), 2)

    def test_match_all_indices(self):
        results = self.matcher.match_all("x")
        indices = sorted(r.index for r in results)
        self.assertEqual(indices, list(range(len(self.candidates))))

    def test_single_candidate(self):
        m = FuzzyMatcher(["hello"])
        r = m.best_match("hello")
        self.assertAlmostEqual(r.score, 1.0)

    def test_empty_query(self):
        results = self.matcher.match("")
        # empty string vs anything => low score
        self.assertIsInstance(results, list)

    def test_case_sensitive(self):
        m = FuzzyMatcher(["Hello", "hello"])
        results = m.match("Hello")
        best = results[0]
        self.assertEqual(best.candidate, "Hello")
        self.assertAlmostEqual(best.score, 1.0)


if __name__ == "__main__":
    unittest.main()
