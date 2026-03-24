"""Tests for SemanticMemoryStore (T579)."""
import time
import tempfile
from pathlib import Path
import pytest
from lidco.memory.semantic_memory import SemanticMemoryStore, MemoryEntry


def test_add_and_get():
    store = SemanticMemoryStore()
    store.add("k1", "Python async programming patterns")
    entry = store.get("k1")
    assert entry is not None
    assert entry.key == "k1"
    assert "Python" in entry.content


def test_get_missing_returns_none():
    store = SemanticMemoryStore()
    assert store.get("nonexistent") is None


def test_delete():
    store = SemanticMemoryStore()
    store.add("k1", "hello world")
    assert store.delete("k1")
    assert store.get("k1") is None


def test_delete_missing_returns_false():
    store = SemanticMemoryStore()
    assert not store.delete("nope")


def test_priority_clamped():
    store = SemanticMemoryStore()
    e1 = store.add("k1", "text", priority=10)
    assert e1.priority == 5
    e2 = store.add("k2", "text", priority=-1)
    assert e2.priority == 1


def test_ttl_expiry():
    store = SemanticMemoryStore()
    store.add("k1", "expires quickly", ttl=0.01)
    time.sleep(0.05)
    assert store.get("k1") is None


def test_ttl_zero_never_expires():
    store = SemanticMemoryStore()
    store.add("k1", "permanent", ttl=0)
    assert store.get("k1") is not None


def test_search_returns_relevant_results():
    store = SemanticMemoryStore()
    store.add("a", "asyncio event loop coroutine python")
    store.add("b", "docker container kubernetes deployment")
    store.add("c", "pytest unit testing coverage python")
    results = store.search("python async coroutine")
    assert len(results) > 0
    keys = [r.entry.key for r in results]
    assert "a" in keys  # most relevant


def test_search_respects_min_priority():
    store = SemanticMemoryStore()
    store.add("low", "python async programming", priority=1)
    store.add("high", "python async programming", priority=5)
    results = store.search("python async", min_priority=3)
    keys = [r.entry.key for r in results]
    assert "high" in keys
    assert "low" not in keys


def test_search_excludes_expired():
    store = SemanticMemoryStore()
    store.add("expired", "python async pattern", ttl=0.01)
    store.add("alive", "python async pattern", ttl=0)
    time.sleep(0.05)
    results = store.search("python async")
    keys = [r.entry.key for r in results]
    assert "expired" not in keys
    assert "alive" in keys


def test_purge_expired():
    store = SemanticMemoryStore()
    store.add("e1", "text", ttl=0.01)
    store.add("e2", "text", ttl=0.01)
    store.add("ok", "text", ttl=0)
    time.sleep(0.05)
    n = store.purge_expired()
    assert n == 2
    assert store.get("ok") is not None


def test_update_priority():
    store = SemanticMemoryStore()
    store.add("k1", "content", priority=2)
    assert store.update_priority("k1", 5)
    entry = store.get("k1")
    assert entry.priority == 5


def test_update_priority_missing_returns_false():
    store = SemanticMemoryStore()
    assert not store.update_priority("nope", 3)


def test_access_count_increments():
    store = SemanticMemoryStore()
    store.add("k1", "content")
    store.get("k1")
    store.get("k1")
    entry = store._entries["k1"]
    assert entry.access_count == 2


def test_max_entries_eviction():
    store = SemanticMemoryStore(max_entries=3)
    store.add("a", "text", priority=1)
    store.add("b", "text", priority=3)
    store.add("c", "text", priority=5)
    store.add("d", "text", priority=4)  # should evict "a" (lowest priority)
    assert len(store.all_entries()) == 3
    assert store.get("a") is None


def test_stats():
    store = SemanticMemoryStore()
    store.add("a", "x", priority=1)
    store.add("b", "x", priority=3)
    store.add("c", "x", priority=5, ttl=3600)
    stats = store.stats()
    assert stats["total"] == 3
    assert stats["with_ttl"] == 1


def test_persistence(tmp_path):
    path = tmp_path / "mem.json"
    store = SemanticMemoryStore(store_path=path)
    store.add("k1", "content to persist", priority=4)
    store.save()

    store2 = SemanticMemoryStore(store_path=path)
    entry = store2.get("k1")
    assert entry is not None
    assert entry.content == "content to persist"
    assert entry.priority == 4


def test_tags_filter_search():
    store = SemanticMemoryStore()
    store.add("t1", "python asyncio code", tags=["python", "async"])
    store.add("t2", "docker deployment ops", tags=["ops"])
    results = store.search("python async", tags=["python"])
    keys = [r.entry.key for r in results]
    assert "t1" in keys
    assert "t2" not in keys
