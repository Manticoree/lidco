"""Tests for ResolutionStore — T474."""
from __future__ import annotations
import pytest
from lidco.review.resolution_store import ResolutionStore


class TestResolutionStore:
    def test_mark_and_check_resolved(self, tmp_path):
        store = ResolutionStore(project_dir=tmp_path)
        store.mark_resolved("use type hints", "a.py", 10)
        assert store.is_resolved("use type hints", "a.py", 10)

    def test_not_resolved_by_default(self, tmp_path):
        store = ResolutionStore(project_dir=tmp_path)
        assert not store.is_resolved("something", "x.py", 1)

    def test_unmark_resolved(self, tmp_path):
        store = ResolutionStore(project_dir=tmp_path)
        store.mark_resolved("b", "f.py", 5)
        store.unmark_resolved("b", "f.py", 5)
        assert not store.is_resolved("b", "f.py", 5)

    def test_list_resolved(self, tmp_path):
        store = ResolutionStore(project_dir=tmp_path)
        store.mark_resolved("a", pr_number="42")
        store.mark_resolved("b", pr_number="42")
        items = store.list_resolved(pr_number="42")
        assert len(items) == 2

    def test_list_all_resolved(self, tmp_path):
        store = ResolutionStore(project_dir=tmp_path)
        store.mark_resolved("a", pr_number="1")
        store.mark_resolved("b", pr_number="2")
        items = store.list_resolved()
        assert len(items) == 2

    def test_clear_removes_all(self, tmp_path):
        store = ResolutionStore(project_dir=tmp_path)
        store.mark_resolved("a")
        store.mark_resolved("b")
        store.clear()
        assert store.list_resolved() == []

    def test_idempotent_mark(self, tmp_path):
        store = ResolutionStore(project_dir=tmp_path)
        store.mark_resolved("a", "f.py", 1)
        store.mark_resolved("a", "f.py", 1)  # duplicate
        items = store.list_resolved()
        assert len(items) == 1
