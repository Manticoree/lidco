"""Tests for MemoryHierarchy — Task 309."""

from __future__ import annotations

import pytest

from lidco.context.memory_hierarchy import LEVELS, MemoryEntry, MemoryHierarchy


# ---------------------------------------------------------------------------
# set() / get()
# ---------------------------------------------------------------------------

class TestMemoryHierarchyBasic:
    def test_set_and_get(self):
        h = MemoryHierarchy()
        h.set("key", "value", level="session")
        assert h.get("key") == "value"

    def test_missing_key_returns_default(self):
        h = MemoryHierarchy()
        assert h.get("missing") is None
        assert h.get("missing", default="fallback") == "fallback"

    def test_invalid_level_raises(self):
        h = MemoryHierarchy()
        with pytest.raises(ValueError, match="Unknown memory level"):
            h.set("key", "val", level="invalid_level")

    def test_all_levels_accepted(self):
        h = MemoryHierarchy()
        for level in LEVELS:
            h.set(f"key_{level}", "val", level=level)

    def test_set_overwrites(self):
        h = MemoryHierarchy()
        h.set("x", "first", level="user")
        h.set("x", "second", level="user")
        assert h.get("x", max_level="user") == "second"


# ---------------------------------------------------------------------------
# Cascade resolution
# ---------------------------------------------------------------------------

class TestMemoryHierarchyCascade:
    def test_session_overrides_user(self):
        h = MemoryHierarchy()
        h.set("style", "pep8", level="user")
        h.set("style", "google", level="session")
        assert h.get("style") == "google"

    def test_project_overrides_org(self):
        h = MemoryHierarchy()
        h.set("db_url", "org-default", level="org")
        h.set("db_url", "project-specific", level="project")
        assert h.get("db_url") == "project-specific"

    def test_max_level_limits_search(self):
        h = MemoryHierarchy()
        h.set("style", "google", level="session")
        h.set("style", "pep8", level="user")
        # Max at "user" → skips session
        assert h.get("style", max_level="user") == "pep8"

    def test_fallback_to_less_specific(self):
        h = MemoryHierarchy()
        h.set("base_url", "org.example.com", level="org")
        # No more specific override
        assert h.get("base_url") == "org.example.com"

    def test_get_entry_returns_full_entry(self):
        h = MemoryHierarchy()
        h.set("tag", "v1", level="project", description="version tag")
        entry = h.get_entry("tag")
        assert entry is not None
        assert entry.key == "tag"
        assert entry.level == "project"
        assert entry.description == "version tag"

    def test_get_at_level_exact(self):
        h = MemoryHierarchy()
        h.set("style", "pep8", level="user")
        h.set("style", "google", level="session")
        assert h.get_at_level("style", "user") == "pep8"
        assert h.get_at_level("style", "session") == "google"
        assert h.get_at_level("style", "org") is None


# ---------------------------------------------------------------------------
# delete() / clear()
# ---------------------------------------------------------------------------

class TestMemoryHierarchyDelete:
    def test_delete_from_level(self):
        h = MemoryHierarchy()
        h.set("k", "v", level="user")
        assert h.delete("k", level="user") is True
        assert h.get("k") is None

    def test_delete_missing_returns_false(self):
        h = MemoryHierarchy()
        assert h.delete("ghost") is False

    def test_delete_all_levels(self):
        h = MemoryHierarchy()
        h.set("k", "a", level="session")
        h.set("k", "b", level="user")
        h.delete("k")  # no level → all
        assert h.get("k") is None

    def test_clear_level(self):
        h = MemoryHierarchy()
        h.set("a", 1, level="session")
        h.set("b", 2, level="session")
        h.set("c", 3, level="user")
        h.clear(level="session")
        assert h.get("a") is None
        assert h.get("c") == 3

    def test_clear_all(self):
        h = MemoryHierarchy()
        for level in LEVELS:
            h.set(f"k_{level}", "v", level=level)
        h.clear()
        assert h.list_keys() == []


# ---------------------------------------------------------------------------
# list_keys() / list_entries()
# ---------------------------------------------------------------------------

class TestMemoryHierarchyList:
    def test_list_keys_at_level(self):
        h = MemoryHierarchy()
        h.set("a", 1, level="user")
        h.set("b", 2, level="user")
        h.set("c", 3, level="session")
        keys = h.list_keys(level="user")
        assert set(keys) == {"a", "b"}

    def test_list_keys_all(self):
        h = MemoryHierarchy()
        h.set("x", 1, level="session")
        h.set("y", 2, level="org")
        keys = h.list_keys()
        assert "x" in keys and "y" in keys

    def test_list_entries_sorted(self):
        h = MemoryHierarchy()
        h.set("z", 1, level="user")
        h.set("a", 2, level="user")
        entries = h.list_entries(level="user")
        names = [e.key for e in entries]
        assert names == sorted(names)


# ---------------------------------------------------------------------------
# effective_snapshot()
# ---------------------------------------------------------------------------

class TestMemoryHierarchySnapshot:
    def test_snapshot_resolves_cascade(self):
        h = MemoryHierarchy()
        h.set("style", "org-style", level="org")
        h.set("style", "session-style", level="session")
        h.set("other", "value", level="user")
        snap = h.effective_snapshot()
        assert snap["style"] == "session-style"
        assert snap["other"] == "value"


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------

class TestMemoryHierarchySearch:
    def test_search_by_key(self):
        h = MemoryHierarchy()
        h.set("auth-token", "sk-xxx", level="session")
        results = h.search("auth")
        assert any(e.key == "auth-token" for e in results)

    def test_search_by_value(self):
        h = MemoryHierarchy()
        h.set("config", "use_postgres=true", level="project")
        results = h.search("postgres")
        assert len(results) == 1

    def test_search_no_match(self):
        h = MemoryHierarchy()
        h.set("key", "value", level="user")
        assert h.search("nonexistent_xyz") == []
