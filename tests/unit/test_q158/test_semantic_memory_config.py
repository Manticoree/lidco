"""Tests for Task 905 — Wire MemoryConfig to SemanticMemoryStore."""

import pytest

from lidco.memory.semantic_memory import SemanticMemoryStore


class TestSemanticMemoryStoreDisabled:
    """When enabled=False, operations are no-ops."""

    def test_add_returns_entry_but_not_stored(self):
        store = SemanticMemoryStore(enabled=False)
        entry = store.add("k1", "test content")
        assert entry.key == "k1"
        assert entry.content == "test content"
        # Not actually stored
        assert store.get("k1") is None

    def test_search_returns_empty(self):
        store = SemanticMemoryStore(enabled=False)
        results = store.search("anything")
        assert results == []

    def test_all_entries_empty_when_disabled(self):
        store = SemanticMemoryStore(enabled=False)
        store.add("k1", "content")
        assert store.all_entries() == []


class TestSemanticMemoryStoreEnabled:
    """enabled=True (default) behaves normally."""

    def test_default_enabled(self):
        store = SemanticMemoryStore()
        assert store._enabled is True

    def test_add_and_get(self):
        store = SemanticMemoryStore()
        store.add("k1", "hello world")
        entry = store.get("k1")
        assert entry is not None
        assert entry.content == "hello world"

    def test_search_finds_entries(self):
        store = SemanticMemoryStore()
        store.add("k1", "python programming language")
        store.add("k2", "java programming language")
        results = store.search("python")
        assert len(results) >= 1
        assert results[0].entry.key == "k1"

    def test_enabled_true_explicit(self):
        store = SemanticMemoryStore(enabled=True)
        store.add("k1", "test")
        assert store.get("k1") is not None


class TestSemanticMemoryStoreMaxEntries:
    """max_entries parameter works with enabled flag."""

    def test_max_entries_respected(self):
        store = SemanticMemoryStore(max_entries=2)
        store.add("k1", "first", priority=1)
        store.add("k2", "second", priority=2)
        store.add("k3", "third", priority=3)
        # Should have evicted lowest priority
        assert len(store.all_entries()) == 2

    def test_max_entries_with_disabled_no_entries(self):
        store = SemanticMemoryStore(max_entries=5, enabled=False)
        for i in range(10):
            store.add(f"k{i}", f"content {i}")
        assert len(store.all_entries()) == 0
