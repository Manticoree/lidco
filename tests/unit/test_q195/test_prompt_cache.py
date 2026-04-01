"""Tests for cache.prompt_cache — CacheEntry, CacheStats, PromptCache."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from lidco.cache.prompt_cache import CacheEntry, CacheStats, PromptCache


class TestCacheEntry(unittest.TestCase):
    def test_frozen(self):
        e = CacheEntry(key="k", value="v", created_at=1.0, ttl=60.0)
        with self.assertRaises(AttributeError):
            e.key = "x"  # type: ignore[misc]

    def test_fields(self):
        e = CacheEntry("k", "v", 100.0, 300.0)
        self.assertEqual(e.key, "k")
        self.assertEqual(e.value, "v")
        self.assertAlmostEqual(e.created_at, 100.0)
        self.assertAlmostEqual(e.ttl, 300.0)


class TestCacheStats(unittest.TestCase):
    def test_frozen(self):
        s = CacheStats(hits=10, misses=5, evictions=2, size=8)
        with self.assertRaises(AttributeError):
            s.hits = 99  # type: ignore[misc]

    def test_fields(self):
        s = CacheStats(1, 2, 3, 4)
        self.assertEqual(s.hits, 1)
        self.assertEqual(s.misses, 2)
        self.assertEqual(s.evictions, 3)
        self.assertEqual(s.size, 4)


class TestPromptCache(unittest.TestCase):
    def test_get_miss(self):
        cache = PromptCache()
        self.assertIsNone(cache.get("missing"))
        self.assertEqual(cache.stats.misses, 1)

    def test_put_and_get(self):
        cache = PromptCache()
        cache.put("key1", "value1")
        self.assertEqual(cache.get("key1"), "value1")
        self.assertEqual(cache.stats.hits, 1)

    def test_evict(self):
        cache = PromptCache()
        cache.put("k", "v")
        self.assertTrue(cache.evict("k"))
        self.assertIsNone(cache.get("k"))

    def test_evict_missing(self):
        cache = PromptCache()
        self.assertFalse(cache.evict("nonexistent"))

    def test_clear(self):
        cache = PromptCache()
        cache.put("a", "1")
        cache.put("b", "2")
        cache.clear()
        self.assertEqual(cache.stats.size, 0)
        self.assertIsNone(cache.get("a"))

    def test_lru_eviction(self):
        cache = PromptCache(max_size=2)
        cache.put("a", "1")
        cache.put("b", "2")
        cache.put("c", "3")
        # "a" should be evicted
        self.assertIsNone(cache.get("a"))
        self.assertEqual(cache.get("b"), "2")
        self.assertEqual(cache.get("c"), "3")
        self.assertEqual(cache.stats.evictions, 1)

    def test_ttl_expiry(self):
        cache = PromptCache(default_ttl=0.01)
        cache.put("k", "v")
        time.sleep(0.02)
        self.assertIsNone(cache.get("k"))

    def test_custom_ttl_per_key(self):
        cache = PromptCache(default_ttl=3600.0)
        cache.put("short", "val", ttl=0.01)
        time.sleep(0.02)
        self.assertIsNone(cache.get("short"))

    def test_stats_initial(self):
        cache = PromptCache()
        s = cache.stats
        self.assertEqual(s.hits, 0)
        self.assertEqual(s.misses, 0)
        self.assertEqual(s.evictions, 0)
        self.assertEqual(s.size, 0)

    def test_overwrite_key(self):
        cache = PromptCache()
        cache.put("k", "v1")
        cache.put("k", "v2")
        self.assertEqual(cache.get("k"), "v2")
        self.assertEqual(cache.stats.size, 1)

    def test_stats_after_operations(self):
        cache = PromptCache()
        cache.put("a", "1")
        cache.get("a")  # hit
        cache.get("b")  # miss
        s = cache.stats
        self.assertEqual(s.hits, 1)
        self.assertEqual(s.misses, 1)
        self.assertEqual(s.size, 1)

    def test_max_size_respected(self):
        cache = PromptCache(max_size=3)
        for i in range(10):
            cache.put(f"k{i}", f"v{i}")
        self.assertLessEqual(cache.stats.size, 3)

    def test_put_then_evict_stats(self):
        cache = PromptCache()
        cache.put("k", "v")
        cache.evict("k")
        self.assertEqual(cache.stats.size, 0)

    def test_default_max_size(self):
        cache = PromptCache()
        self.assertEqual(cache._max_size, 1000)

    def test_default_ttl(self):
        cache = PromptCache()
        self.assertAlmostEqual(cache._default_ttl, 3600.0)


class TestPromptCacheAllExport(unittest.TestCase):
    def test_all(self):
        from lidco.cache import prompt_cache

        self.assertIn("CacheEntry", prompt_cache.__all__)
        self.assertIn("CacheStats", prompt_cache.__all__)
        self.assertIn("PromptCache", prompt_cache.__all__)


if __name__ == "__main__":
    unittest.main()
