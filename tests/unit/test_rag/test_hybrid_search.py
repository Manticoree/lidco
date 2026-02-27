"""Tests for BM25 index and hybrid semantic+BM25 search."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lidco.rag.bm25 import BM25Index, _tokenize
from lidco.rag.indexer import CodeChunk
from lidco.rag.store import SearchResult, _reciprocal_rank_fusion


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_chunk(name: str, content: str, start_line: int = 1) -> CodeChunk:
    return CodeChunk(
        file_path=f"/proj/{name}.py",
        content=content,
        language="python",
        chunk_type="function",
        start_line=start_line,
        end_line=start_line + 5,
        name=name,
    )


def _make_result(name: str, content: str, score: float = 0.9) -> SearchResult:
    chunk = _make_chunk(name, content)
    return SearchResult(chunk=chunk, score=score, distance=1.0 - score)


# ── _tokenize ─────────────────────────────────────────────────────────────────


class TestTokenize:
    def test_splits_words(self) -> None:
        assert _tokenize("hello world") == ["hello", "world"]

    def test_lowercases(self) -> None:
        assert _tokenize("CamelCase") == ["camelcase"]

    def test_handles_underscores(self) -> None:
        tokens = _tokenize("context_deduplicator")
        assert "context_deduplicator" in tokens

    def test_ignores_punctuation(self) -> None:
        tokens = _tokenize("foo.bar(baz)")
        assert "foo" in tokens and "bar" in tokens and "baz" in tokens
        assert "." not in tokens

    def test_empty_string(self) -> None:
        assert _tokenize("") == []


# ── BM25Index ─────────────────────────────────────────────────────────────────


class TestBM25Index:
    def test_empty_index_returns_empty(self) -> None:
        idx = BM25Index()
        assert idx.search("anything", n_results=5) == []

    def test_size_reflects_entries(self) -> None:
        idx = BM25Index()
        idx.add_many([("a", "alpha"), ("b", "beta")])
        assert idx.size == 2

    def test_search_returns_chunk_id_score_pairs(self) -> None:
        idx = BM25Index()
        idx.add_many([("chunk1", "context deduplicator class python")])
        results = idx.search("context deduplicator", n_results=5)
        assert len(results) == 1
        cid, score = results[0]
        assert cid == "chunk1"
        assert 0.0 <= score <= 1.0

    def test_max_score_normalised_to_1(self) -> None:
        # Need at least 3 docs so df=1 gives IDF > 0 (with N=2, IDF = log(1) = 0)
        idx = BM25Index()
        idx.add_many([
            ("exact", "context deduplicator"),
            ("unrelated1", "banana smoothie recipe"),
            ("unrelated2", "coffee table furniture"),
        ])
        results = idx.search("context deduplicator", n_results=10)
        assert len(results) >= 1
        # Top result should have score == 1.0 (normalised)
        assert results[0][1] == pytest.approx(1.0)

    def test_relevant_chunk_ranks_higher_than_unrelated(self) -> None:
        idx = BM25Index()
        idx.add_many([
            ("relevant", "def context_deduplicator(): deduplicate context"),
            ("irrelevant", "def foo(): banana apple orange"),
        ])
        results = idx.search("context deduplicator", n_results=10)
        chunk_ids = [cid for cid, _ in results]
        assert chunk_ids.index("relevant") < chunk_ids.index("irrelevant")

    def test_remove_ids_drops_entries(self) -> None:
        idx = BM25Index()
        idx.add_many([("keep", "important code"), ("drop", "remove this")])
        idx.remove_ids({"drop"})
        assert idx.size == 1
        results = idx.search("remove", n_results=5)
        assert all(cid != "drop" for cid, _ in results)

    def test_remove_ids_missing_ids_no_error(self) -> None:
        idx = BM25Index()
        idx.add_many([("a", "hello")])
        idx.remove_ids({"nonexistent"})
        assert idx.size == 1

    def test_clear_empties_index(self) -> None:
        idx = BM25Index()
        idx.add_many([("a", "code"), ("b", "more code")])
        idx.clear()
        assert idx.size == 0
        assert idx.search("code", n_results=5) == []

    def test_empty_query_returns_empty(self) -> None:
        idx = BM25Index()
        idx.add_many([("a", "hello world")])
        assert idx.search("", n_results=5) == []

    def test_graceful_when_rank_bm25_missing(self) -> None:
        """When rank_bm25 is not installed, search returns []."""
        idx = BM25Index()
        idx.add_many([("a", "hello world")])
        with patch.dict("sys.modules", {"rank_bm25": None}):
            # Simulate import failure inside _rebuild_if_needed
            import sys
            original = sys.modules.get("rank_bm25")
            try:
                sys.modules["rank_bm25"] = None  # type: ignore[assignment]
                idx._dirty = True
                idx._bm25 = None
                result = idx.search("hello", n_results=5)
                # Should not raise; may return [] or partial results
                assert isinstance(result, list)
            finally:
                if original is None:
                    sys.modules.pop("rank_bm25", None)
                else:
                    sys.modules["rank_bm25"] = original
                # Reset the class-level unavailability flag so subsequent tests
                # that rely on rank_bm25 being importable are not affected.
                BM25Index._rank_bm25_unavailable = False

    def test_search_respects_n_results_limit(self) -> None:
        idx = BM25Index()
        idx.add_many([(f"chunk{i}", f"def function_{i}: code here") for i in range(20)])
        results = idx.search("function code", n_results=5)
        assert len(results) <= 5


# ── _reciprocal_rank_fusion ───────────────────────────────────────────────────


class TestReciprocalRankFusion:
    def test_empty_inputs_return_empty(self) -> None:
        assert _reciprocal_rank_fusion([], [], bm25_weight=0.4) == []

    def test_only_semantic_results(self) -> None:
        r1 = _make_result("auth", "def authenticate()")
        merged = _reciprocal_rank_fusion([r1], [], bm25_weight=0.4)
        assert len(merged) == 1
        assert merged[0].chunk.name == "auth"

    def test_only_bm25_results(self) -> None:
        r1 = _make_result("token", "class Token:")
        merged = _reciprocal_rank_fusion([], [r1], bm25_weight=0.4)
        assert len(merged) == 1

    def test_chunk_in_both_lists_appears_once(self) -> None:
        r = _make_result("shared", "def shared_function()")
        merged = _reciprocal_rank_fusion([r], [r], bm25_weight=0.4)
        assert len(merged) == 1

    def test_chunk_in_both_lists_scores_higher(self) -> None:
        """A chunk appearing in both lists should rank higher than one in only one."""
        shared = _make_result("shared", "def shared_context_deduplicator()")
        semantic_only = _make_result("semantic_only", "def alpha_func()", score=0.95)

        # shared is in both lists, semantic_only is only in semantic
        merged = _reciprocal_rank_fusion(
            semantic_results=[semantic_only, shared],
            bm25_results=[shared],
            bm25_weight=0.4,
        )
        names = [r.chunk.name for r in merged]
        assert names.index("shared") < names.index("semantic_only")

    def test_ordering_is_deterministic(self) -> None:
        r1 = _make_result("a", "alpha function")
        r2 = _make_result("b", "beta function")
        m1 = _reciprocal_rank_fusion([r1, r2], [r1], bm25_weight=0.4)
        m2 = _reciprocal_rank_fusion([r1, r2], [r1], bm25_weight=0.4)
        assert [r.chunk.name for r in m1] == [r.chunk.name for r in m2]

    def test_bm25_weight_zero_uses_semantic_only(self) -> None:
        """With bm25_weight=0, BM25 contributes nothing; semantic order preserved."""
        r1 = _make_result("first", "def first()")
        r2 = _make_result("second", "def second()")
        # r2 is top in BM25
        merged = _reciprocal_rank_fusion([r1, r2], [r2, r1], bm25_weight=0.0)
        assert merged[0].chunk.name == "first"


# ── VectorStore.search_hybrid ─────────────────────────────────────────────────


class TestVectorStoreSearchHybrid:
    """Unit tests for search_hybrid using a mocked ChromaDB collection."""

    def _make_store(self) -> "VectorStore":  # noqa: F821
        """Return a VectorStore with ChromaDB stubbed out."""
        from lidco.rag.store import VectorStore

        with patch("lidco.rag.store.VectorStore._init_chromadb"):
            store = VectorStore.__new__(VectorStore)
            store._persist_dir = MagicMock()
            store._bm25 = BM25Index()
            store._chunk_cache = {}
            # Minimal collection mock
            mock_col = MagicMock()
            mock_col.count.return_value = 0
            store._collection = mock_col
            store._client = MagicMock()
            return store

    def test_returns_semantic_when_bm25_empty(self) -> None:
        from lidco.rag.store import VectorStore

        store = self._make_store()
        sem_result = _make_result("sem", "def sem_func()")
        with patch.object(VectorStore, "search", return_value=[sem_result]):
            results = store.search_hybrid("query", n_results=5)
        assert results == [sem_result]

    def test_hybrid_merges_bm25_and_semantic(self) -> None:
        from lidco.rag.store import VectorStore

        store = self._make_store()

        sem_chunk = _make_chunk("semantic_only", "def semantic_only(): pass", start_line=1)
        bm25_chunk = _make_chunk("bm25_only", "def bm25_only(): pass", start_line=10)

        # Add BM25 chunk to index
        bm25_id = "bm25fakeid"
        store._bm25.add_many([(bm25_id, bm25_chunk.content)])
        store._chunk_cache[bm25_id] = bm25_chunk

        sem_result = SearchResult(chunk=sem_chunk, score=0.9, distance=0.1)

        with (
            patch.object(VectorStore, "search", return_value=[sem_result]),
            patch.object(store._bm25, "search", return_value=[(bm25_id, 1.0)]),
        ):
            results = store.search_hybrid("query", n_results=10)

        names = {r.chunk.name for r in results}
        assert "semantic_only" in names
        assert "bm25_only" in names

    def test_language_filter_excludes_other_languages(self) -> None:
        from lidco.rag.store import VectorStore

        store = self._make_store()

        js_chunk = CodeChunk(
            file_path="/proj/app.js",
            content="function jsFunc() {}",
            language="javascript",
            chunk_type="function",
            start_line=1,
            end_line=5,
            name="jsFunc",
        )
        bm25_id = "js_chunk_id"
        store._bm25.add_many([(bm25_id, js_chunk.content)])
        store._chunk_cache[bm25_id] = js_chunk

        with (
            patch.object(VectorStore, "search", return_value=[]),
            patch.object(store._bm25, "search", return_value=[(bm25_id, 1.0)]),
        ):
            results = store.search_hybrid("query", n_results=10, filter_language="python")

        # JS chunk should be filtered out
        assert all(r.chunk.language == "python" for r in results)

    def test_unknown_chunk_id_in_bm25_ignored(self) -> None:
        """BM25 returns a chunk_id not in cache — should be skipped."""
        from lidco.rag.store import VectorStore

        store = self._make_store()
        sem_result = _make_result("fallback", "def fallback(): pass")

        with (
            patch.object(VectorStore, "search", return_value=[sem_result]),
            patch.object(store._bm25, "search", return_value=[("ghost_id", 0.8)]),
        ):
            results = store.search_hybrid("query", n_results=10)

        # ghost_id has no cache entry → BM25 contributes nothing → semantic used
        assert results == [sem_result]

    def test_path_prefix_excludes_bm25_results_outside_prefix(self) -> None:
        """BM25 hits with file_path not matching path_prefix are excluded."""
        from lidco.rag.store import VectorStore

        store = self._make_store()

        cli_chunk = CodeChunk(
            file_path="src/lidco/cli/app.py",
            content="def run(): pass",
            language="python",
            chunk_type="function",
            start_line=1,
            end_line=5,
            name="run",
        )
        rag_chunk = CodeChunk(
            file_path="src/lidco/rag/store.py",
            content="def search(): pass",
            language="python",
            chunk_type="function",
            start_line=1,
            end_line=5,
            name="search",
        )
        cli_id, rag_id = "cli_id", "rag_id"
        store._bm25.add_many([(cli_id, cli_chunk.content), (rag_id, rag_chunk.content)])
        store._chunk_cache[cli_id] = cli_chunk
        store._chunk_cache[rag_id] = rag_chunk

        with (
            patch.object(VectorStore, "search", return_value=[]),
            patch.object(store._bm25, "search", return_value=[(cli_id, 0.9), (rag_id, 0.8)]),
        ):
            results = store.search_hybrid("query", n_results=10, path_prefix="src/lidco/cli/")

        # Only cli/ chunk should be present
        paths = {r.chunk.file_path for r in results}
        assert "src/lidco/cli/app.py" in paths
        assert "src/lidco/rag/store.py" not in paths


# ── ContextRetriever.retrieve uses search_hybrid ──────────────────────────────


class TestRetrieverUsesHybridSearch:
    def test_retrieve_delegates_to_search_hybrid(self) -> None:
        from lidco.rag.retriever import ContextRetriever

        mock_store = MagicMock()
        mock_store.search_hybrid.return_value = []
        mock_indexer = MagicMock()

        retriever = ContextRetriever(
            store=mock_store,
            indexer=mock_indexer,
            project_dir=MagicMock(),
        )

        retriever.retrieve("find ContextDeduplicator")

        mock_store.search_hybrid.assert_called_once()
        # Ensure plain search() is NOT called
        mock_store.search.assert_not_called()


# ── BM25 persistence ──────────────────────────────────────────────────────────


class TestBM25Persistence:
    """save() / load() round-trip for BM25Index corpus."""

    def test_save_and_load_round_trip(self, tmp_path) -> None:
        idx = BM25Index()
        idx.add_many([
            ("a", "context deduplicator"),
            ("b", "token budget enforcement"),
            ("c", "hybrid search bm25"),
        ])
        pkl = tmp_path / "bm25.pkl"
        idx.save(pkl)

        idx2 = BM25Index()
        assert idx2.load(pkl) is True
        assert idx2.size == 3

    def test_load_missing_file_returns_false(self, tmp_path) -> None:
        idx = BM25Index()
        assert idx.load(tmp_path / "nonexistent.pkl") is False

    def test_load_corrupt_file_returns_false(self, tmp_path) -> None:
        pkl = tmp_path / "bad.pkl"
        pkl.write_bytes(b"not a pickle")
        idx = BM25Index()
        assert idx.load(pkl) is False

    def test_loaded_index_can_search(self, tmp_path) -> None:
        idx = BM25Index()
        idx.add_many([
            ("chunk_a", "context deduplicator"),
            ("chunk_b", "banana smoothie"),
            ("chunk_c", "coffee table"),
        ])
        pkl = tmp_path / "bm25.pkl"
        idx.save(pkl)

        idx2 = BM25Index()
        idx2.load(pkl)
        results = idx2.search("context deduplicator", n_results=5)
        assert len(results) >= 1
        assert results[0][0] == "chunk_a"

    def test_save_overwrites_existing_file(self, tmp_path) -> None:
        pkl = tmp_path / "bm25.pkl"
        idx = BM25Index()
        idx.add_many([("x", "foo bar")])
        idx.save(pkl)

        idx2 = BM25Index()
        idx2.add_many([("y", "baz qux"), ("z", "hello world")])
        idx2.save(pkl)

        idx3 = BM25Index()
        idx3.load(pkl)
        assert idx3.size == 2

    def test_load_empty_corpus(self, tmp_path) -> None:
        idx = BM25Index()
        pkl = tmp_path / "empty.pkl"
        idx.save(pkl)

        idx2 = BM25Index()
        assert idx2.load(pkl) is True
        assert idx2.size == 0

    def test_wrong_format_returns_false(self, tmp_path) -> None:
        import pickle as _pickle
        pkl = tmp_path / "wrong.pkl"
        with open(pkl, "wb") as f:
            _pickle.dump({"not": "a list"}, f)
        idx = BM25Index()
        assert idx.load(pkl) is False


# ── BM25 incremental rebuild (Task 39) ────────────────────────────────────────


class TestBM25IncrementalRebuild:
    """Tests for the incremental rebuild optimisation in BM25Index."""

    def _large_corpus(self, n: int = 100) -> list[tuple[str, str]]:
        return [(f"id_{i}", f"document content number {i} with unique token tok_{i}") for i in range(n)]

    def test_dirty_count_increments_on_add(self) -> None:
        idx = BM25Index()
        idx.add_many([("a", "hello"), ("b", "world")])
        assert idx._dirty_count == 2

    def test_dirty_count_increments_on_remove(self) -> None:
        idx = BM25Index()
        idx.add_many([("a", "hello"), ("b", "world")])
        idx.search("hello", 5)  # triggers rebuild, resets dirty_count
        idx.remove_ids({"a"})
        assert idx._dirty_count == 1

    def test_dirty_count_reset_after_full_rebuild(self) -> None:
        idx = BM25Index()
        idx.add_many([("a", "hello")])
        idx.search("hello", 5)
        assert idx._dirty_count == 0
        assert not idx._dirty

    def test_dirty_count_reset_on_clear(self) -> None:
        idx = BM25Index()
        idx.add_many([("a", "hello")])
        idx.clear()
        assert idx._dirty_count == 0

    def test_small_mutation_skips_rebuild(self) -> None:
        """Adding 1 doc to 100-doc corpus (1% dirty) must reuse the existing model."""
        from unittest.mock import patch
        from rank_bm25 import BM25Okapi  # skip if not installed

        idx = BM25Index()
        idx.add_many(self._large_corpus(100))
        idx.search("content", 5)  # builds initial model
        model_before = idx._bm25

        # Add 1 more (1% dirty ratio < 10% threshold)
        idx.add_many([("new_one", "brand new document")])
        idx.search("content", 5)

        # Model object must be the same (not rebuilt)
        assert idx._bm25 is model_before

    def test_large_mutation_triggers_full_rebuild(self) -> None:
        """Adding 20 docs to 100-doc corpus (20% dirty) must trigger full rebuild."""
        try:
            from rank_bm25 import BM25Okapi  # noqa: F401
        except ImportError:
            pytest.skip("rank_bm25 not installed")

        idx = BM25Index()
        idx.add_many(self._large_corpus(100))
        idx.search("content", 5)  # builds initial model
        model_before = idx._bm25

        # Add 20 more (20% dirty ratio ≥ 10% threshold)
        idx.add_many(self._large_corpus(20))
        idx.search("content", 5)

        # Model must have been rebuilt
        assert idx._bm25 is not model_before

    def test_no_model_yet_always_triggers_full_rebuild(self) -> None:
        """First search always builds the model regardless of dirty_count."""
        try:
            from rank_bm25 import BM25Okapi  # noqa: F401
        except ImportError:
            pytest.skip("rank_bm25 not installed")

        idx = BM25Index()
        idx.add_many([("a", "hello")])
        assert idx._bm25 is None
        idx.search("hello", 5)
        assert idx._bm25 is not None
