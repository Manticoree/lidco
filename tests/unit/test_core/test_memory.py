"""Tests for persistent memory system."""

import pytest
from datetime import datetime, timedelta, timezone
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


class TestMemoryTTL:
    """Tests for Memory TTL / expiry (Task 44)."""

    def _old_iso(self, days: int) -> str:
        """Return an ISO timestamp that is ``days`` days in the past."""
        ts = datetime.now(timezone.utc) - timedelta(days=days)
        return ts.isoformat()

    def test_fresh_entry_not_expired(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "m", ttl_days=30)
        entry = MemoryEntry(
            key="k", content="v",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        assert store._is_expired(entry) is False

    def test_old_entry_expired(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "m", ttl_days=7)
        entry = MemoryEntry(key="k", content="v", created_at=self._old_iso(10))
        assert store._is_expired(entry) is True

    def test_no_ttl_never_expires(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "m", ttl_days=None)
        entry = MemoryEntry(key="k", content="v", created_at=self._old_iso(3650))
        assert store._is_expired(entry) is False

    def test_empty_created_at_not_expired(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "m", ttl_days=1)
        entry = MemoryEntry(key="k", content="v", created_at="")
        assert store._is_expired(entry) is False

    def test_expired_excluded_from_list_all(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "m", ttl_days=7)
        store._entries["old"] = MemoryEntry(
            key="old", content="stale", created_at=self._old_iso(10)
        )
        store._entries["fresh"] = MemoryEntry(
            key="fresh", content="new",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        result = store.list_all()
        keys = {e.key for e in result}
        assert "fresh" in keys
        assert "old" not in keys

    def test_expired_excluded_from_search(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "m", ttl_days=7)
        store._entries["old"] = MemoryEntry(
            key="old", content="keyword", created_at=self._old_iso(10)
        )
        store._entries["fresh"] = MemoryEntry(
            key="fresh", content="keyword",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        results = store.search("keyword")
        keys = {e.key for e in results}
        assert "fresh" in keys
        assert "old" not in keys

    def test_expired_excluded_from_build_context(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "m", ttl_days=7)
        store._entries["stale"] = MemoryEntry(
            key="stale", content="old_value", created_at=self._old_iso(10)
        )
        store._entries["live"] = MemoryEntry(
            key="live", content="live_value",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        ctx = store.build_context_string()
        assert "live_value" in ctx
        assert "old_value" not in ctx

    def test_prune_expired_removes_from_dict(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "m", ttl_days=7)
        store._entries["old"] = MemoryEntry(
            key="old", content="v", created_at=self._old_iso(10)
        )
        store._entries["new"] = MemoryEntry(
            key="new", content="v",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        removed = store.prune_expired()
        assert removed == 1
        assert "old" not in store._entries
        assert "new" in store._entries

    def test_prune_expired_returns_zero_when_nothing_expired(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "m", ttl_days=30)
        store._entries["fresh"] = MemoryEntry(
            key="fresh", content="v",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        assert store.prune_expired() == 0

    def test_save_prunes_expired_from_disk(self, tmp_path):
        mem_dir = tmp_path / "m"
        store = MemoryStore(global_dir=mem_dir, ttl_days=7)
        # Add a fresh entry via the public API (writes to disk)
        store.add(key="keeper", content="keep me", category="test")
        # Manually inject an expired entry into the JSON file
        import json
        cat_file = mem_dir / "test.json"
        data = json.loads(cat_file.read_text())
        data.append({
            "key": "expired_one",
            "content": "delete me",
            "category": "test",
            "tags": [],
            "created_at": self._old_iso(10),
            "source": "",
        })
        cat_file.write_text(json.dumps(data))
        # Writing a new entry triggers pruning on save
        store._entries["expired_one"] = MemoryEntry(
            key="expired_one", content="delete me",
            created_at=self._old_iso(10), category="test",
        )
        store.add(key="another", content="another", category="test")
        # Reload from disk — expired entry must be gone
        store2 = MemoryStore(global_dir=mem_dir, ttl_days=7)
        assert store2.get("expired_one") is None
        assert store2.get("keeper") is not None
