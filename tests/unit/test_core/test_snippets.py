"""Tests for SnippetStore."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from lidco.core.snippets import SnippetEntry, SnippetStore


def _store(tmp_path: Path) -> SnippetStore:
    return SnippetStore(tmp_path / ".lidco" / "snippets.json")


class TestSnippetStoreAdd:
    def test_add_returns_entry(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        entry = store.add("foo", "print('hello')", language="python")
        assert entry.key == "foo"
        assert entry.content == "print('hello')"
        assert entry.language == "python"

    def test_add_creates_json_file(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        store.add("k", "v")
        assert (tmp_path / ".lidco" / "snippets.json").exists()

    def test_add_with_tags(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        entry = store.add("foo", "code", tags=["auth", "jwt"])
        assert entry.tags == ["auth", "jwt"]

    def test_overwrite_existing_key(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        store.add("k", "old")
        store.add("k", "new")
        assert store.get("k").content == "new"
        assert len(store) == 1

    def test_created_at_is_set(self, tmp_path: Path) -> None:
        before = time.time()
        store = _store(tmp_path)
        entry = store.add("k", "v")
        assert entry.created_at >= before


class TestSnippetStoreGet:
    def test_get_existing(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        store.add("foo", "bar")
        assert store.get("foo").content == "bar"

    def test_get_missing_returns_none(self, tmp_path: Path) -> None:
        assert _store(tmp_path).get("nonexistent") is None


class TestSnippetStoreDelete:
    def test_delete_removes_entry(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        store.add("k", "v")
        assert store.delete("k") is True
        assert store.get("k") is None

    def test_delete_missing_returns_false(self, tmp_path: Path) -> None:
        assert _store(tmp_path).delete("ghost") is False

    def test_delete_persists(self, tmp_path: Path) -> None:
        path = tmp_path / ".lidco" / "snippets.json"
        store = _store(tmp_path)
        store.add("k", "v")
        store.delete("k")
        store2 = SnippetStore(path)
        assert store2.get("k") is None


class TestSnippetStoreList:
    def test_list_all_sorted_newest_first(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        store.add("a", "1")
        store.add("b", "2")
        keys = [e.key for e in store.list_all()]
        assert keys == ["b", "a"]

    def test_list_filter_by_tag(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        store.add("a", "1", tags=["auth"])
        store.add("b", "2", tags=["db"])
        store.add("c", "3", tags=["auth", "jwt"])
        result = store.list_all(tag="auth")
        assert {e.key for e in result} == {"a", "c"}

    def test_list_empty_store(self, tmp_path: Path) -> None:
        assert _store(tmp_path).list_all() == []


class TestSnippetStoreSearch:
    def test_search_by_key(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        store.add("jwt_auth", "...")
        store.add("db_pool", "...")
        result = store.search("jwt")
        assert len(result) == 1
        assert result[0].key == "jwt_auth"

    def test_search_by_content(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        store.add("k", "SELECT * FROM users WHERE id = ?")
        result = store.search("users")
        assert len(result) == 1

    def test_search_by_tag(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        store.add("k", "x", tags=["security"])
        result = store.search("security")
        assert len(result) == 1

    def test_search_case_insensitive(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        store.add("MyFunc", "code")
        assert len(store.search("myfunc")) == 1


class TestSnippetStorePersistence:
    def test_reload_from_disk(self, tmp_path: Path) -> None:
        path = tmp_path / ".lidco" / "snippets.json"
        store1 = SnippetStore(path)
        store1.add("k", "v", language="py", tags=["t"])

        store2 = SnippetStore(path)
        entry = store2.get("k")
        assert entry is not None
        assert entry.content == "v"
        assert entry.language == "py"
        assert entry.tags == ["t"]

    def test_handles_corrupt_json(self, tmp_path: Path) -> None:
        path = tmp_path / ".lidco" / "snippets.json"
        path.parent.mkdir(parents=True)
        path.write_text("NOT JSON")
        store = SnippetStore(path)  # must not raise
        assert len(store) == 0
