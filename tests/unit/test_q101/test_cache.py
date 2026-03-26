"""Tests for src/lidco/core/cache.py — LRUCache."""
import time
import pytest
from lidco.core.cache import LRUCache, CacheStats


class TestLRUCacheBasic:
    def test_set_and_get(self):
        c = LRUCache(maxsize=10)
        c.set("a", 1)
        assert c.get("a") == 1

    def test_get_missing_returns_default(self):
        c = LRUCache(maxsize=10)
        assert c.get("x") is None
        assert c.get("x", 42) == 42

    def test_overwrite_key(self):
        c = LRUCache(maxsize=10)
        c.set("k", "v1")
        c.set("k", "v2")
        assert c.get("k") == "v2"

    def test_delete_existing(self):
        c = LRUCache(maxsize=10)
        c.set("k", "v")
        assert c.delete("k") is True
        assert c.get("k") is None

    def test_delete_missing(self):
        c = LRUCache(maxsize=10)
        assert c.delete("nonexistent") is False

    def test_contains(self):
        c = LRUCache(maxsize=10)
        c.set("a", 1)
        assert "a" in c
        assert "b" not in c

    def test_len(self):
        c = LRUCache(maxsize=10)
        assert len(c) == 0
        c.set("a", 1)
        c.set("b", 2)
        assert len(c) == 2

    def test_keys(self):
        c = LRUCache(maxsize=10)
        c.set("b", 2)
        c.set("a", 1)
        keys = c.keys()
        assert set(keys) == {"a", "b"}

    def test_clear(self):
        c = LRUCache(maxsize=10)
        c.set("a", 1)
        c.clear()
        assert len(c) == 0


class TestLRUEviction:
    def test_evicts_lru_on_overflow(self):
        c = LRUCache(maxsize=3)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        # Access "a" to make it recently used
        c.get("a")
        c.set("d", 4)  # should evict "b" (LRU)
        assert c.get("b") is None
        assert c.get("a") == 1
        assert c.get("c") == 3
        assert c.get("d") == 4

    def test_eviction_increments_stats(self):
        c = LRUCache(maxsize=2)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        s = c.stats()
        assert s.evictions >= 1


class TestLRUTTL:
    def test_ttl_expires(self):
        c = LRUCache(maxsize=10, ttl=0.05)
        c.set("k", "v")
        assert c.get("k") == "v"
        time.sleep(0.1)
        assert c.get("k") is None

    def test_per_key_ttl_override(self):
        c = LRUCache(maxsize=10, ttl=10.0)
        c.set("fast", "v", ttl=0.05)
        c.set("slow", "v2")
        time.sleep(0.1)
        assert c.get("fast") is None
        assert c.get("slow") == "v2"

    def test_no_global_ttl_by_default(self):
        c = LRUCache(maxsize=10)
        c.set("k", "v")
        time.sleep(0.05)
        assert c.get("k") == "v"


class TestLRUStats:
    def test_hits_and_misses(self):
        c = LRUCache(maxsize=10)
        c.set("a", 1)
        c.get("a")   # hit
        c.get("b")   # miss
        s = c.stats()
        assert s.hits == 1
        assert s.misses == 1

    def test_hit_rate_computed(self):
        c = LRUCache(maxsize=10)
        c.set("a", 1)
        c.get("a")  # hit
        c.get("b")  # miss
        s = c.stats()
        total = s.hits + s.misses
        assert total == 2
        assert s.hits == 1

    def test_zero_hits_when_no_lookups(self):
        c = LRUCache(maxsize=10)
        s = c.stats()
        assert s.hits == 0
        assert s.misses == 0

    def test_stats_type(self):
        c = LRUCache(maxsize=10)
        assert isinstance(c.stats(), CacheStats)

    def test_stats_size(self):
        c = LRUCache(maxsize=42)
        c.set("a", 1)
        assert c.stats().size == 1
