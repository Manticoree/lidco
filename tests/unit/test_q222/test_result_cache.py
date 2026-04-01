"""Tests for lidco.tools.result_cache."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from lidco.tools.result_cache import CacheEntry, ToolResultCache


class TestCacheEntry(unittest.TestCase):
    def test_frozen(self) -> None:
        entry = CacheEntry(key="k", tool_name="t", result="r")
        with self.assertRaises(AttributeError):
            entry.key = "new"  # type: ignore[misc]

    def test_defaults(self) -> None:
        entry = CacheEntry(key="k", tool_name="t", result="r")
        self.assertEqual(entry.ttl, 300.0)
        self.assertEqual(entry.hit_count, 0)
        self.assertGreater(entry.created_at, 0)


class TestToolResultCache(unittest.TestCase):
    def test_put_and_get(self) -> None:
        cache = ToolResultCache()
        cache.put("grep", "pattern", "found it")
        self.assertEqual(cache.get("grep", "pattern"), "found it")

    def test_get_miss(self) -> None:
        cache = ToolResultCache()
        self.assertIsNone(cache.get("grep", "nope"))
        self.assertEqual(cache.stats()["misses"], 1)

    def test_hit_count_increments(self) -> None:
        cache = ToolResultCache()
        cache.put("t", "a", "res")
        cache.get("t", "a")
        cache.get("t", "a")
        key = cache._make_key("t", "a")
        self.assertEqual(cache._entries[key].hit_count, 2)

    def test_ttl_expiration(self) -> None:
        cache = ToolResultCache(default_ttl=0.01)
        cache.put("t", "a", "res")
        time.sleep(0.02)
        self.assertIsNone(cache.get("t", "a"))

    def test_custom_ttl(self) -> None:
        cache = ToolResultCache()
        entry = cache.put("t", "a", "res", ttl=999.0)
        self.assertEqual(entry.ttl, 999.0)

    def test_invalidate(self) -> None:
        cache = ToolResultCache()
        cache.put("t", "a", "res")
        self.assertTrue(cache.invalidate("t", "a"))
        self.assertFalse(cache.invalidate("t", "a"))
        self.assertIsNone(cache.get("t", "a"))

    def test_invalidate_by_tool(self) -> None:
        cache = ToolResultCache()
        cache.put("grep", "a", "r1")
        cache.put("grep", "b", "r2")
        cache.put("read", "c", "r3")
        self.assertEqual(cache.invalidate_by_tool("grep"), 2)
        self.assertEqual(cache.stats()["size"], 1)

    def test_evict_expired(self) -> None:
        cache = ToolResultCache(default_ttl=0.01)
        cache.put("t", "a", "r")
        cache.put("t", "b", "r")
        time.sleep(0.02)
        count = cache.evict_expired()
        self.assertEqual(count, 2)
        self.assertEqual(cache.stats()["size"], 0)

    def test_max_size_eviction(self) -> None:
        cache = ToolResultCache(max_size=3)
        for i in range(5):
            cache.put("t", str(i), f"r{i}")
        self.assertLessEqual(cache.stats()["size"], 3)

    def test_clear(self) -> None:
        cache = ToolResultCache()
        cache.put("t", "a", "r")
        cache.get("t", "a")
        cache.clear()
        s = cache.stats()
        self.assertEqual(s["size"], 0)
        self.assertEqual(s["hits"], 0)

    def test_summary(self) -> None:
        cache = ToolResultCache()
        cache.put("t", "a", "r")
        cache.get("t", "a")
        summary = cache.summary()
        self.assertIn("ToolResultCache", summary)
        self.assertIn("1 hits", summary)

    def test_make_key_deterministic(self) -> None:
        cache = ToolResultCache()
        k1 = cache._make_key("t", "args")
        k2 = cache._make_key("t", "args")
        self.assertEqual(k1, k2)
        k3 = cache._make_key("t", "other")
        self.assertNotEqual(k1, k3)


if __name__ == "__main__":
    unittest.main()
