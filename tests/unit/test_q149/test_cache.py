"""Tests for CompletionCache."""
from __future__ import annotations
import time
import unittest
from unittest.mock import patch
from lidco.completion.cache import CompletionCache, CacheEntry


class TestCacheEntry(unittest.TestCase):
    def test_defaults(self):
        entry = CacheEntry(prefix="he", results=["hello"], timestamp=1.0)
        self.assertEqual(entry.hit_count, 0)

    def test_fields(self):
        entry = CacheEntry(prefix="ab", results=["abc"], timestamp=2.0, hit_count=5)
        self.assertEqual(entry.prefix, "ab")
        self.assertEqual(entry.hit_count, 5)


class TestCompletionCache(unittest.TestCase):
    def setUp(self):
        self.cache = CompletionCache(max_size=5, ttl=10.0)

    # --- get / put ---

    def test_put_and_get(self):
        self.cache.put("he", ["hello", "help"])
        result = self.cache.get("he")
        self.assertEqual(result, ["hello", "help"])

    def test_get_miss(self):
        self.assertIsNone(self.cache.get("nope"))

    def test_get_returns_copy(self):
        self.cache.put("ab", ["abc"])
        r1 = self.cache.get("ab")
        r1.append("xyz")
        r2 = self.cache.get("ab")
        self.assertEqual(r2, ["abc"])

    def test_put_updates_existing(self):
        self.cache.put("he", ["hello"])
        self.cache.put("he", ["help"])
        result = self.cache.get("he")
        self.assertEqual(result, ["help"])

    # --- ttl ---

    def test_ttl_expiry(self):
        self.cache.put("x", ["xray"])
        with patch("lidco.completion.cache.time.monotonic", return_value=time.monotonic() + 20):
            result = self.cache.get("x")
        self.assertIsNone(result)

    def test_ttl_not_expired(self):
        self.cache.put("x", ["xray"])
        result = self.cache.get("x")
        self.assertEqual(result, ["xray"])

    # --- eviction ---

    def test_lru_eviction(self):
        for i in range(6):
            self.cache.put(f"k{i}", [f"v{i}"])
        # k0 should have been evicted (max_size=5)
        self.assertIsNone(self.cache.get("k0"))
        self.assertIsNotNone(self.cache.get("k5"))

    def test_evict_expired(self):
        self.cache.put("old", ["data"])
        with patch("lidco.completion.cache.time.monotonic", return_value=time.monotonic() + 20):
            count = self.cache.evict_expired()
        self.assertEqual(count, 1)

    def test_evict_expired_none_stale(self):
        self.cache.put("fresh", ["data"])
        count = self.cache.evict_expired()
        self.assertEqual(count, 0)

    # --- invalidate ---

    def test_invalidate_specific(self):
        self.cache.put("a", ["1"])
        self.cache.put("b", ["2"])
        self.cache.invalidate("a")
        self.assertIsNone(self.cache.get("a"))
        self.assertIsNotNone(self.cache.get("b"))

    def test_invalidate_all(self):
        self.cache.put("a", ["1"])
        self.cache.put("b", ["2"])
        self.cache.invalidate()
        self.assertIsNone(self.cache.get("a"))
        self.assertIsNone(self.cache.get("b"))

    def test_invalidate_nonexistent(self):
        self.cache.invalidate("nope")  # should not raise

    # --- stats ---

    def test_stats_initial(self):
        stats = self.cache.stats()
        self.assertEqual(stats["hits"], 0)
        self.assertEqual(stats["misses"], 0)
        self.assertEqual(stats["size"], 0)

    def test_stats_after_hits(self):
        self.cache.put("x", ["y"])
        self.cache.get("x")
        self.cache.get("x")
        stats = self.cache.stats()
        self.assertEqual(stats["hits"], 2)
        self.assertEqual(stats["hit_rate"], 1.0)

    def test_stats_after_miss(self):
        self.cache.get("nope")
        stats = self.cache.stats()
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["hit_rate"], 0.0)

    # --- warm ---

    def test_warm(self):
        self.cache.warm([("a", ["apple"]), ("b", ["banana"])])
        self.assertEqual(self.cache.get("a"), ["apple"])
        self.assertEqual(self.cache.get("b"), ["banana"])

    def test_warm_empty(self):
        self.cache.warm([])
        self.assertEqual(self.cache.stats()["size"], 0)


if __name__ == "__main__":
    unittest.main()
