"""Tests for persistent memory system."""

import pytest
from pathlib import Path

from lidco.core.memory import MemoryStore, MemoryEntry


class TestMemoryEntry:
    def test_to_dict(self):
        entry = MemoryEntry(
            key="test", content="hello", category="general", tags=("a", "b")
        )
        d = entry.to_dict()
        assert d["key"] == "test"
        assert d["content"] == "hello"
        assert d["tags"] == ["a", "b"]

    def test_from_dict(self):
        entry = MemoryEntry.from_dict({
            "key": "test",
            "content": "hello",
            "category": "pattern",
            "tags": ["x"],
        })
        assert entry.key == "test"
        assert entry.category == "pattern"
        assert entry.tags == ("x",)

    def test_roundtrip(self):
        entry = MemoryEntry(key="k", content="c", category="decision", tags=("t",))
        restored = MemoryEntry.from_dict(entry.to_dict())
        assert restored.key == entry.key
        assert restored.content == entry.content
        assert restored.category == entry.category
        assert restored.tags == entry.tags


class TestMemoryStore:
    def test_add_and_get(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "memory", max_entries=100)
        store.add(key="test_key", content="test_value")
        entry = store.get("test_key")
        assert entry is not None
        assert entry.content == "test_value"

    def test_persistence(self, tmp_path):
        mem_dir = tmp_path / "memory"
        store1 = MemoryStore(global_dir=mem_dir, max_entries=100)
        store1.add(key="persist", content="survives restart")

        store2 = MemoryStore(global_dir=mem_dir, max_entries=100)
        entry = store2.get("persist")
        assert entry is not None
        assert entry.content == "survives restart"

    def test_search(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "memory", max_entries=100)
        store.add(key="pattern_1", content="always use immutable objects")
        store.add(key="pattern_2", content="validate input at boundaries")
        store.add(key="other", content="unrelated note")

        results = store.search("immutable")
        assert len(results) == 1
        assert results[0].key == "pattern_1"

    def test_search_by_category(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "memory", max_entries=100)
        store.add(key="a", content="x", category="pattern")
        store.add(key="b", content="x", category="decision")

        results = store.search("x", category="pattern")
        assert len(results) == 1
        assert results[0].key == "a"

    def test_list_all(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "memory", max_entries=100)
        store.add(key="k1", content="v1")
        store.add(key="k2", content="v2")
        all_entries = store.list_all()
        assert len(all_entries) == 2

    def test_remove(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "memory", max_entries=100)
        store.add(key="removeme", content="temp")
        assert store.remove("removeme") is True
        assert store.get("removeme") is None

    def test_remove_nonexistent(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "memory", max_entries=100)
        assert store.remove("nope") is False

    def test_build_context_string(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "memory", max_entries=100)
        store.add(key="tip1", content="use frozen dataclasses", category="pattern")
        ctx = store.build_context_string()
        assert "tip1" in ctx
        assert "frozen dataclasses" in ctx

    def test_max_entries_enforcement(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "memory", max_entries=5)
        for i in range(10):
            store.add(key=f"entry_{i}", content=f"value_{i}", category="test")

        # After reload, only last 5 should remain
        store2 = MemoryStore(global_dir=tmp_path / "memory", max_entries=5)
        all_entries = store2.list_all()
        assert len(all_entries) <= 5

    def test_memory_md_loaded(self, tmp_path):
        mem_dir = tmp_path / "memory"
        mem_dir.mkdir()
        (mem_dir / "MEMORY.md").write_text("# Important\nAlways use TypeScript.")
        store = MemoryStore(global_dir=mem_dir, max_entries=100)
        ctx = store.build_context_string()
        assert "Always use TypeScript" in ctx
