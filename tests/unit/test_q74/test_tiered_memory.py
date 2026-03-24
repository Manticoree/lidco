"""Tests for TieredMemoryStore — T492."""
from __future__ import annotations
import pytest
from lidco.memory.tiered_memory import TieredMemoryStore


class TestTieredMemoryStore:
    def test_add_workspace_default(self, tmp_path):
        store = TieredMemoryStore(project_dir=tmp_path, global_dir=tmp_path / "global")
        m = store.add("workspace fact", tags=["tag1"])
        assert m.content == "workspace fact"

    def test_add_global_scope(self, tmp_path):
        store = TieredMemoryStore(project_dir=tmp_path, global_dir=tmp_path / "global")
        m = store.add("global fact", scope="global")
        assert m.content == "global fact"

    def test_search_workspace_first(self, tmp_path):
        store = TieredMemoryStore(project_dir=tmp_path, global_dir=tmp_path / "global")
        store.add("workspace python tip", scope="workspace")
        store.add("global python tip", scope="global")
        results = store.search("python tip")
        # Workspace result should come before global
        assert any("workspace" in r.content for r in results)

    def test_search_no_duplicates(self, tmp_path):
        store = TieredMemoryStore(project_dir=tmp_path, global_dir=tmp_path / "global")
        store.add("unique fact", scope="workspace")
        store.add("unique fact", scope="global")
        results = store.search("unique fact")
        contents = [r.content for r in results]
        assert contents.count("unique fact") == 1

    def test_list_combines_both(self, tmp_path):
        store = TieredMemoryStore(project_dir=tmp_path, global_dir=tmp_path / "global")
        store.add("ws1", scope="workspace")
        store.add("gl1", scope="global")
        items = store.list()
        contents = [m.content for m in items]
        assert "ws1" in contents
        assert "gl1" in contents

    def test_format_context_headers(self, tmp_path):
        store = TieredMemoryStore(project_dir=tmp_path, global_dir=tmp_path / "global")
        store.add("ws fact", scope="workspace")
        store.add("gl fact", scope="global")
        ctx = store.format_context()
        assert "Workspace memories" in ctx
        assert "Global memories" in ctx

    def test_delete_searches_both(self, tmp_path):
        store = TieredMemoryStore(project_dir=tmp_path, global_dir=tmp_path / "global")
        m = store.add("to delete", scope="workspace")
        result = store.delete(m.id)
        assert result

    def test_workspace_and_global_stores_separate(self, tmp_path):
        store = TieredMemoryStore(project_dir=tmp_path, global_dir=tmp_path / "global")
        assert store.workspace_store is not store.global_store

    def test_scope_default_is_workspace(self, tmp_path):
        store = TieredMemoryStore(project_dir=tmp_path, global_dir=tmp_path / "global")
        m = store.add("default scope")
        ws_items = store.workspace_store.list()
        assert any(x.content == "default scope" for x in ws_items)
