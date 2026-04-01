"""Tests for lidco.query.cache (Q199)."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from lidco.query.cache import CacheEntry, QueryCache


class TestQueryCache(unittest.TestCase):
    def setUp(self):
        self.cache = QueryCache(max_size=5, ttl_seconds=1.0)

    def test_put_and_get(self):
        self.cache.put("q1", {"data": [1, 2]})
        result = self.cache.get("q1")
        self.assertEqual(result, {"data": [1, 2]})

    def test_get_miss(self):
        result = self.cache.get("nonexistent")
        self.assertIsNone(result)

    def test_ttl_expiry(self):
        self.cache.put("q1", "value")
        # Patch time.monotonic to simulate expiry
        original_get = self.cache.get
        entry = self.cache._entries["q1"]
        entry.created_at = time.monotonic() - 2.0  # expired
        result = self.cache.get("q1")
        self.assertIsNone(result)

    def test_file_invalidation(self):
        self.cache.put("q1", "val1", file_paths=("a.py", "b.py"))
        self.cache.put("q2", "val2", file_paths=("b.py",))
        self.cache.put("q3", "val3", file_paths=("c.py",))
        count = self.cache.invalidate_file("b.py")
        self.assertEqual(count, 2)
        self.assertIsNone(self.cache.get("q1"))
        self.assertIsNone(self.cache.get("q2"))
        self.assertEqual(self.cache.get("q3"), "val3")

    def test_invalidate_all(self):
        self.cache.put("q1", "v1")
        self.cache.put("q2", "v2")
        count = self.cache.invalidate_all()
        self.assertEqual(count, 2)
        self.assertIsNone(self.cache.get("q1"))
        self.assertIsNone(self.cache.get("q2"))

    def test_evict_expired(self):
        self.cache.put("q1", "v1")
        self.cache.put("q2", "v2")
        # force expire
        for e in self.cache._entries.values():
            e.created_at = time.monotonic() - 2.0
        evicted = self.cache.evict_expired()
        self.assertEqual(evicted, 2)
        self.assertEqual(len(self.cache._entries), 0)

    def test_max_size_eviction(self):
        for i in range(6):
            self.cache.put(f"q{i}", f"v{i}")
        # max_size=5, so first entry should be evicted
        self.assertEqual(len(self.cache._entries), 5)
        self.assertIsNone(self.cache.get("q0"))
        self.assertEqual(self.cache.get("q5"), "v5")

    def test_stats(self):
        self.cache.put("q1", "v1")
        self.cache.get("q1")  # hit
        self.cache.get("q2")  # miss
        s = self.cache.stats()
        self.assertEqual(s["hits"], 1)
        self.assertEqual(s["misses"], 1)
        self.assertEqual(s["size"], 1)

    def test_clear(self):
        self.cache.put("q1", "v1")
        self.cache.get("q1")
        self.cache.clear()
        s = self.cache.stats()
        self.assertEqual(s["size"], 0)
        self.assertEqual(s["hits"], 0)


if __name__ == "__main__":
    unittest.main()
