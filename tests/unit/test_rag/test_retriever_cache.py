"""Tests for ContextRetriever retrieve() LRU cache with TTL."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lidco.rag.retriever import ContextRetriever, _CACHE_MAX


def _make_retriever(ttl: float = 30.0) -> tuple[ContextRetriever, MagicMock]:
    """Return a retriever backed by a mock store and a reference to that mock."""
    store = MagicMock()
    store.search_hybrid.return_value = []
    indexer = MagicMock()
    retriever = ContextRetriever(
        store=store,
        indexer=indexer,
        project_dir=Path("/tmp/test"),
        cache_ttl=ttl,
    )
    return retriever, store


class TestRetrieveCacheHit:
    def test_second_call_does_not_hit_store(self):
        retriever, store = _make_retriever()
        retriever.retrieve("some query")
        retriever.retrieve("some query")
        assert store.search_hybrid.call_count == 1

    def test_different_query_hits_store_again(self):
        retriever, store = _make_retriever()
        retriever.retrieve("query A")
        retriever.retrieve("query B")
        assert store.search_hybrid.call_count == 2

    def test_different_max_results_bypasses_cache(self):
        retriever, store = _make_retriever()
        retriever.retrieve("query", max_results=5)
        retriever.retrieve("query", max_results=10)
        assert store.search_hybrid.call_count == 2

    def test_different_filter_language_bypasses_cache(self):
        retriever, store = _make_retriever()
        retriever.retrieve("query", filter_language="python")
        retriever.retrieve("query", filter_language="typescript")
        assert store.search_hybrid.call_count == 2

    def test_none_vs_string_filter_are_different_keys(self):
        retriever, store = _make_retriever()
        retriever.retrieve("query", filter_language=None)
        retriever.retrieve("query", filter_language="python")
        assert store.search_hybrid.call_count == 2

    def test_different_path_prefix_bypasses_cache(self):
        retriever, store = _make_retriever()
        retriever.retrieve("query", path_prefix="src/cli/")
        retriever.retrieve("query", path_prefix="src/rag/")
        assert store.search_hybrid.call_count == 2

    def test_same_path_prefix_uses_cache(self):
        retriever, store = _make_retriever()
        retriever.retrieve("query", path_prefix="src/cli/")
        retriever.retrieve("query", path_prefix="src/cli/")
        assert store.search_hybrid.call_count == 1

    def test_path_prefix_forwarded_to_store(self):
        retriever, store = _make_retriever()
        retriever.retrieve("query", path_prefix="src/agents/")
        call_kwargs = store.search_hybrid.call_args
        assert call_kwargs.kwargs.get("path_prefix") == "src/agents/"


class TestRetrieveCacheTTL:
    def test_expired_entry_triggers_new_search(self):
        retriever, store = _make_retriever(ttl=30.0)
        # First call — populates cache
        retriever.retrieve("q")
        assert store.search_hybrid.call_count == 1

        # Simulate time passing beyond TTL by backdating the cache entry
        key = ("q", 10, None, None, False)
        ts, val = retriever._retrieve_cache[key]
        retriever._retrieve_cache[key] = (ts - 31.0, val)  # expired

        retriever.retrieve("q")
        assert store.search_hybrid.call_count == 2

    def test_fresh_entry_is_served_from_cache(self):
        retriever, store = _make_retriever(ttl=30.0)
        retriever.retrieve("q")
        # Entry was just created — still fresh
        retriever.retrieve("q")
        assert store.search_hybrid.call_count == 1


class TestRetrieveCacheInvalidation:
    def test_index_project_invalidates_cache(self):
        retriever, store = _make_retriever()
        store.search_hybrid.return_value = []
        indexer = retriever._indexer
        indexer.get_supported_extensions.return_value = {".py"}
        indexer.index_directory.return_value = []

        retriever.retrieve("q")
        assert store.search_hybrid.call_count == 1

        retriever.index_project()

        retriever.retrieve("q")
        assert store.search_hybrid.call_count == 2

    def test_clear_invalidates_cache(self):
        retriever, store = _make_retriever()
        retriever.retrieve("q")
        assert store.search_hybrid.call_count == 1

        retriever.clear()
        retriever.retrieve("q")
        assert store.search_hybrid.call_count == 2

    def test_update_file_invalidates_cache(self, tmp_path: Path):
        retriever, store = _make_retriever()
        f = tmp_path / "a.py"
        f.write_text("x = 1")
        retriever._indexer.index_file.return_value = []

        retriever.retrieve("q")
        assert store.search_hybrid.call_count == 1

        retriever.update_file(f)
        retriever.retrieve("q")
        assert store.search_hybrid.call_count == 2


class TestRetrieveCacheEviction:
    def test_cache_does_not_grow_beyond_max(self):
        retriever, store = _make_retriever()
        for i in range(_CACHE_MAX + 10):
            retriever.retrieve(f"unique query {i}")
        assert len(retriever._retrieve_cache) <= _CACHE_MAX

    def test_oldest_entry_evicted_when_full(self):
        retriever, store = _make_retriever()
        # Fill cache to capacity
        for i in range(_CACHE_MAX):
            retriever.retrieve(f"query_{i}")
        # Backdating the very first entry so it is oldest
        first_key = ("query_0", 10, None, None, False)
        ts, val = retriever._retrieve_cache[first_key]
        retriever._retrieve_cache[first_key] = (ts - 1000.0, val)

        # One more unique query should evict the oldest
        retriever.retrieve("brand_new_query")
        assert first_key not in retriever._retrieve_cache

