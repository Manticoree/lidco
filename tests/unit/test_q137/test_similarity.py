"""Tests for Q137 SimilarityMetrics."""
from __future__ import annotations
import unittest
from lidco.text.similarity import SimilarityMetrics, SimilarityResult


class TestSimilarityResult(unittest.TestCase):
    def test_fields(self):
        r = SimilarityResult(score=0.9, method="ratio", details={"a": 1})
        self.assertEqual(r.score, 0.9)
        self.assertEqual(r.method, "ratio")
        self.assertEqual(r.details, {"a": 1})

    def test_default_details(self):
        r = SimilarityResult(score=0.5, method="x")
        self.assertEqual(r.details, {})


class TestLevenshtein(unittest.TestCase):
    def test_identical(self):
        self.assertEqual(SimilarityMetrics.levenshtein("abc", "abc"), 0)

    def test_empty_a(self):
        self.assertEqual(SimilarityMetrics.levenshtein("", "abc"), 3)

    def test_empty_b(self):
        self.assertEqual(SimilarityMetrics.levenshtein("abc", ""), 3)

    def test_both_empty(self):
        self.assertEqual(SimilarityMetrics.levenshtein("", ""), 0)

    def test_single_insert(self):
        self.assertEqual(SimilarityMetrics.levenshtein("abc", "abcd"), 1)

    def test_single_delete(self):
        self.assertEqual(SimilarityMetrics.levenshtein("abcd", "abc"), 1)

    def test_single_replace(self):
        self.assertEqual(SimilarityMetrics.levenshtein("abc", "axc"), 1)

    def test_kitten_sitting(self):
        self.assertEqual(SimilarityMetrics.levenshtein("kitten", "sitting"), 3)

    def test_symmetric(self):
        self.assertEqual(
            SimilarityMetrics.levenshtein("abc", "xyz"),
            SimilarityMetrics.levenshtein("xyz", "abc"),
        )


class TestRatio(unittest.TestCase):
    def test_identical(self):
        self.assertAlmostEqual(SimilarityMetrics.ratio("abc", "abc"), 1.0)

    def test_completely_different(self):
        r = SimilarityMetrics.ratio("aaa", "zzz")
        self.assertLess(r, 0.5)

    def test_empty_both(self):
        self.assertAlmostEqual(SimilarityMetrics.ratio("", ""), 1.0)

    def test_returns_float(self):
        self.assertIsInstance(SimilarityMetrics.ratio("a", "b"), float)


class TestJaccard(unittest.TestCase):
    def test_identical(self):
        self.assertAlmostEqual(SimilarityMetrics.jaccard("a b c", "a b c"), 1.0)

    def test_no_overlap(self):
        self.assertAlmostEqual(SimilarityMetrics.jaccard("a b", "c d"), 0.0)

    def test_partial_overlap(self):
        j = SimilarityMetrics.jaccard("a b c", "b c d")
        self.assertAlmostEqual(j, 2 / 4)

    def test_both_empty(self):
        self.assertAlmostEqual(SimilarityMetrics.jaccard("", ""), 1.0)

    def test_one_empty(self):
        self.assertAlmostEqual(SimilarityMetrics.jaccard("a", ""), 0.0)


class TestCosine(unittest.TestCase):
    def test_identical(self):
        self.assertAlmostEqual(SimilarityMetrics.cosine("a b c", "a b c"), 1.0)

    def test_no_overlap(self):
        self.assertAlmostEqual(SimilarityMetrics.cosine("a b", "c d"), 0.0)

    def test_both_empty(self):
        self.assertAlmostEqual(SimilarityMetrics.cosine("", ""), 0.0)

    def test_one_empty(self):
        self.assertAlmostEqual(SimilarityMetrics.cosine("a", ""), 0.0)

    def test_returns_between_0_and_1(self):
        c = SimilarityMetrics.cosine("hello world", "hello there")
        self.assertGreaterEqual(c, 0.0)
        self.assertLessEqual(c, 1.0)


class TestCompare(unittest.TestCase):
    def test_returns_dict(self):
        result = SimilarityMetrics.compare("abc", "abd")
        self.assertIsInstance(result, dict)

    def test_has_all_keys(self):
        result = SimilarityMetrics.compare("abc", "abd")
        for key in ("levenshtein", "ratio", "jaccard", "cosine"):
            self.assertIn(key, result)

    def test_levenshtein_is_int(self):
        result = SimilarityMetrics.compare("abc", "abd")
        self.assertIsInstance(result["levenshtein"], int)

    def test_ratio_is_float(self):
        result = SimilarityMetrics.compare("abc", "abd")
        self.assertIsInstance(result["ratio"], float)


if __name__ == "__main__":
    unittest.main()
