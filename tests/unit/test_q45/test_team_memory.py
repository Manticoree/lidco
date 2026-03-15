"""Tests for TeamMemoryStore — Task 311."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from lidco.context.team_memory import TeamMemoryEntry, TeamMemoryStore


# ---------------------------------------------------------------------------
# set / get / delete
# ---------------------------------------------------------------------------

class TestTeamMemoryStoreCRUD:
    def test_set_and_get(self):
        store = TeamMemoryStore(path="/tmp/nonexistent.md")
        entry = store.set("db-url", "postgresql://localhost/mydb")
        assert store.get("db-url") is not None
        assert entry.content == "postgresql://localhost/mydb"

    def test_get_missing_returns_none(self):
        store = TeamMemoryStore(path="/tmp/nonexistent.md")
        assert store.get("ghost") is None

    def test_set_with_tags(self):
        store = TeamMemoryStore(path="/tmp/nonexistent.md")
        store.set("key", "val", tags=["infra", "db"])
        entry = store.get("key")
        assert "infra" in entry.tags
        assert "db" in entry.tags

    def test_set_with_description(self):
        store = TeamMemoryStore(path="/tmp/nonexistent.md")
        store.set("key", "val", description="important key")
        assert store.get("key").description == "important key"

    def test_set_overwrites(self):
        store = TeamMemoryStore(path="/tmp/nonexistent.md")
        store.set("k", "first")
        store.set("k", "second")
        assert store.get("k").content == "second"

    def test_delete_existing(self):
        store = TeamMemoryStore(path="/tmp/nonexistent.md")
        store.set("k", "v")
        assert store.delete("k") is True
        assert store.get("k") is None

    def test_delete_missing_returns_false(self):
        store = TeamMemoryStore(path="/tmp/nonexistent.md")
        assert store.delete("ghost") is False

    def test_count(self):
        store = TeamMemoryStore(path="/tmp/nonexistent.md")
        assert store.count() == 0
        store.set("a", "1")
        store.set("b", "2")
        assert store.count() == 2


# ---------------------------------------------------------------------------
# load / save
# ---------------------------------------------------------------------------

class TestTeamMemoryStoreIO:
    def test_load_nonexistent_returns_0(self, tmp_path):
        store = TeamMemoryStore(path=tmp_path / "missing.md")
        n = store.load()
        assert n == 0

    def test_save_and_reload(self, tmp_path):
        path = tmp_path / "team-memory.md"
        store = TeamMemoryStore(path=path)
        store.set("oncall", "Alice → Bob")
        store.set("style", "pep8")
        store.save()

        # Reload from file
        store2 = TeamMemoryStore(path=path)
        n = store2.load()
        assert n == 2
        assert store2.get("oncall") is not None
        assert "Alice" in store2.get("oncall").content

    def test_save_creates_parent_dir(self, tmp_path):
        path = tmp_path / "nested" / "dir" / "team-memory.md"
        store = TeamMemoryStore(path=path)
        store.set("k", "v")
        store.save()
        assert path.exists()

    def test_load_parses_basic_md(self, tmp_path):
        path = tmp_path / "tm.md"
        path.write_text(textwrap.dedent("""\
            # Team Memory

            ## [key] oncall
            Alice → Bob → Carol

            ## [key] style
            Use PEP-8 and ruff.
        """), encoding="utf-8")
        store = TeamMemoryStore(path=path)
        n = store.load()
        assert n == 2
        assert store.get("oncall") is not None
        assert store.get("style") is not None

    def test_load_parses_tags_from_yaml(self, tmp_path):
        path = tmp_path / "tm.md"
        path.write_text(textwrap.dedent("""\
            # Team Memory

            ## [key] db-url
            tags: [infra, db]
            description: Main DB

            postgresql://localhost/prod
        """), encoding="utf-8")
        store = TeamMemoryStore(path=path)
        store.load()
        entry = store.get("db-url")
        assert entry is not None
        assert "infra" in entry.tags


# ---------------------------------------------------------------------------
# list_entries / search
# ---------------------------------------------------------------------------

class TestTeamMemoryStoreListSearch:
    def test_list_entries_sorted(self):
        store = TeamMemoryStore(path="/tmp/x.md")
        store.set("z", "last")
        store.set("a", "first")
        store.set("m", "middle")
        keys = [e.key for e in store.list_entries()]
        assert keys == sorted(keys)

    def test_search_by_key(self):
        store = TeamMemoryStore(path="/tmp/x.md")
        store.set("oncall-rotation", "Alice")
        results = store.search("oncall")
        assert len(results) == 1
        assert results[0].key == "oncall-rotation"

    def test_search_by_content(self):
        store = TeamMemoryStore(path="/tmp/x.md")
        store.set("policy", "never commit secrets to git")
        results = store.search("secrets")
        assert len(results) == 1

    def test_search_no_match(self):
        store = TeamMemoryStore(path="/tmp/x.md")
        store.set("k", "v")
        assert store.search("xyz_nonexistent") == []

    def test_search_by_tag(self):
        store = TeamMemoryStore(path="/tmp/x.md")
        store.set("db-url", "postgres://...", tags=["infra"])
        results = store.search("infra")
        assert len(results) == 1
