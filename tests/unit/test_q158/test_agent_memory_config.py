"""Tests for Task 904 — Wire MemoryConfig to AgentMemoryStore."""

import tempfile
from pathlib import Path

import pytest

from lidco.memory.agent_memory import AgentMemoryStore


class TestAgentMemoryStoreDisabled:
    """When enabled=False, store operations are no-ops."""

    def test_add_returns_memory_but_no_db(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "test.db"
            store = AgentMemoryStore(db_path=db, enabled=False)
            m = store.add("hello", tags=["t1"])
            assert m.content == "hello"
            # DB file should not be created
            assert not db.exists()

    def test_search_returns_empty_when_disabled(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "test.db"
            store = AgentMemoryStore(db_path=db, enabled=False)
            assert store.search("anything") == []

    def test_list_returns_empty_when_disabled(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "test.db"
            store = AgentMemoryStore(db_path=db, enabled=False)
            assert store.list() == []


class TestAgentMemoryStoreMaxEntries:
    """max_entries limits stored memories."""

    def test_max_entries_evicts_oldest(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            db = Path(td) / "test.db"
            store = AgentMemoryStore(db_path=db, max_entries=3)
            for i in range(5):
                store.add(f"memory {i}")
            all_mems = store.list(limit=100)
            assert len(all_mems) == 3

    def test_max_entries_zero_means_unlimited(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            db = Path(td) / "test.db"
            store = AgentMemoryStore(db_path=db, max_entries=0)
            for i in range(10):
                store.add(f"memory {i}")
            all_mems = store.list(limit=100)
            assert len(all_mems) == 10


class TestAgentMemoryStoreDefaults:
    """Default behavior (no config params) unchanged."""

    def test_default_enabled_true(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            db = Path(td) / "test.db"
            store = AgentMemoryStore(db_path=db)
            assert store._enabled is True

    def test_default_max_entries_zero(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            db = Path(td) / "test.db"
            store = AgentMemoryStore(db_path=db)
            assert store._max_entries == 0

    def test_add_and_search_work_by_default(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            db = Path(td) / "test.db"
            store = AgentMemoryStore(db_path=db)
            store.add("test content", tags=["tag1"])
            results = store.search("test")
            assert len(results) == 1
            assert results[0].content == "test content"
