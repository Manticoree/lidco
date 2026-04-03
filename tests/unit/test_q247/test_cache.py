"""Tests for lidco.response.cache."""
from __future__ import annotations

import unittest

from lidco.response.cache import ResponseCache, _word_overlap


class TestWordOverlap(unittest.TestCase):
    """Tests for the _word_overlap helper."""

    def test_identical(self) -> None:
        self.assertAlmostEqual(_word_overlap("hello world", "hello world"), 1.0)

    def test_disjoint(self) -> None:
        self.assertAlmostEqual(_word_overlap("hello", "world"), 0.0)

    def test_partial(self) -> None:
        score = _word_overlap("hello world", "hello there")
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)

    def test_empty(self) -> None:
        self.assertAlmostEqual(_word_overlap("", "hello"), 0.0)


class TestResponseCache(unittest.TestCase):
    """Tests for ResponseCache."""

    def setUp(self) -> None:
        self.cache = ResponseCache(max_size=4)

    # -- put / get ---------------------------------------------------------

    def test_put_and_get(self) -> None:
        self.cache.put("prompt1", "response1")
        self.assertEqual(self.cache.get("prompt1"), "response1")

    def test_get_miss(self) -> None:
        self.assertIsNone(self.cache.get("nonexistent"))

    def test_put_overwrite(self) -> None:
        self.cache.put("p", "old")
        self.cache.put("p", "new")
        self.assertEqual(self.cache.get("p"), "new")

    def test_eviction(self) -> None:
        for i in range(5):
            self.cache.put(f"p{i}", f"r{i}")
        # p0 should have been evicted (max_size=4)
        self.assertIsNone(self.cache.get("p0"))
        self.assertEqual(self.cache.get("p4"), "r4")

    # -- get_similar -------------------------------------------------------

    def test_get_similar_hit(self) -> None:
        self.cache.put("how to sort a list in python", "Use sorted().")
        result = self.cache.get_similar("how to sort a python list")
        self.assertEqual(result, "Use sorted().")

    def test_get_similar_miss(self) -> None:
        self.cache.put("hello world", "greeting")
        result = self.cache.get_similar("completely different topic")
        self.assertIsNone(result)

    def test_get_similar_threshold(self) -> None:
        self.cache.put("a b c d e", "resp")
        # Only 1 word overlap out of many
        result = self.cache.get_similar("a x y z w", threshold=0.9)
        self.assertIsNone(result)

    # -- invalidate --------------------------------------------------------

    def test_invalidate_existing(self) -> None:
        self.cache.put("p", "r")
        self.assertTrue(self.cache.invalidate("p"))
        self.assertIsNone(self.cache.get("p"))

    def test_invalidate_missing(self) -> None:
        self.assertFalse(self.cache.invalidate("nope"))

    # -- clear -------------------------------------------------------------

    def test_clear(self) -> None:
        self.cache.put("p", "r")
        self.cache.clear()
        s = self.cache.stats()
        self.assertEqual(s["hits"], 0)
        self.assertEqual(s["misses"], 0)
        self.assertEqual(s["size"], 0)

    def test_clear_removes_entries(self) -> None:
        self.cache.put("p", "r")
        self.cache.clear()
        self.assertIsNone(self.cache.get("p"))

    # -- stats -------------------------------------------------------------

    def test_stats_initial(self) -> None:
        s = self.cache.stats()
        self.assertEqual(s, {"hits": 0, "misses": 0, "size": 0})

    def test_stats_after_operations(self) -> None:
        self.cache.put("p", "r")
        self.cache.get("p")       # hit
        self.cache.get("missing")  # miss
        s = self.cache.stats()
        self.assertEqual(s["hits"], 1)
        self.assertEqual(s["misses"], 1)
        self.assertEqual(s["size"], 1)

    def test_stats_size_tracks_entries(self) -> None:
        self.cache.put("a", "1")
        self.cache.put("b", "2")
        self.assertEqual(self.cache.stats()["size"], 2)


if __name__ == "__main__":
    unittest.main()
