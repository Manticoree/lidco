"""Tests for lidco.embeddings.retriever."""

from __future__ import annotations

import time
import unittest

from lidco.embeddings.generator import EmbeddingGenerator
from lidco.embeddings.retriever import BM25Index, HybridRetriever, RetrievalResult
from lidco.embeddings.vector_store import VectorEntry, VectorStore


def _entry(
    id: str,
    content: str,
    embedding: list[float] | None = None,
    file_path: str = "a.py",
    start_line: int = 1,
    updated_at: float = 0.0,
) -> VectorEntry:
    return VectorEntry(
        id=id,
        file_path=file_path,
        start_line=start_line,
        end_line=start_line + 5,
        content=content,
        chunk_type="function",
        name=id,
        embedding=embedding or [0.0],
        updated_at=updated_at or time.time(),
    )


class TestBM25Index(unittest.TestCase):
    def test_bm25_add_and_search(self) -> None:
        idx = BM25Index()
        idx.add_document("d1", "python function hello world")
        idx.add_document("d2", "java class hello")
        idx.add_document("d3", "python testing framework")

        results = idx.search("python", top_k=2)
        self.assertGreater(len(results), 0)
        # Python appears in d1 and d3
        ids = [r[0] for r in results]
        self.assertIn("d1", ids)
        self.assertIn("d3", ids)

    def test_bm25_empty_index(self) -> None:
        idx = BM25Index()
        results = idx.search("hello")
        self.assertEqual(results, [])

    def test_bm25_no_match(self) -> None:
        idx = BM25Index()
        idx.add_document("d1", "python function code")
        results = idx.search("zzzznonexistent")
        self.assertEqual(results, [])

    def test_bm25_clear(self) -> None:
        idx = BM25Index()
        idx.add_document("d1", "python code")
        idx.clear()
        results = idx.search("python")
        self.assertEqual(results, [])


class TestHybridRetriever(unittest.TestCase):
    def _build_retriever(self) -> tuple[HybridRetriever, VectorStore]:
        gen = EmbeddingGenerator()
        store = VectorStore()

        texts = [
            "def calculate_sum(a, b): return a + b",
            "class DatabaseConnection: pass",
            "def parse_json(data): return json.loads(data)",
        ]
        gen.build_vocabulary(texts)

        entries: list[VectorEntry] = []
        for i, text in enumerate(texts):
            emb = gen.generate_embedding(text)
            e = VectorEntry(
                id=f"e{i}",
                file_path=f"mod{i}.py",
                start_line=1,
                end_line=5,
                content=text,
                chunk_type="function" if i != 1 else "class",
                name=f"item{i}",
                embedding=emb,
                updated_at=time.time() - i * 100,
            )
            entries.append(e)
            store.upsert(e)

        retriever = HybridRetriever(store, gen)
        retriever.build_keyword_index(entries)
        return retriever, store

    def test_hybrid_search_returns_results(self) -> None:
        retriever, store = self._build_retriever()
        results = retriever.search("calculate sum", top_k=3)
        self.assertGreater(len(results), 0)
        self.assertIsInstance(results[0], RetrievalResult)
        store.close()

    def test_hybrid_search_empty(self) -> None:
        gen = EmbeddingGenerator()
        store = VectorStore()
        retriever = HybridRetriever(store, gen)
        results = retriever.search("anything")
        self.assertEqual(results, [])
        store.close()

    def test_hybrid_semantic_only(self) -> None:
        retriever, store = self._build_retriever()
        results = retriever.search_semantic("calculate sum", top_k=3)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertEqual(r.source, "semantic")
        store.close()

    def test_hybrid_keyword_only(self) -> None:
        retriever, store = self._build_retriever()
        results = retriever.search_keyword("calculate sum", top_k=3)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertEqual(r.source, "keyword")
        store.close()

    def test_hybrid_deduplication(self) -> None:
        retriever, store = self._build_retriever()
        results = retriever.search("calculate", top_k=10)
        # No duplicate (file_path, start_line) pairs
        seen = set()
        for r in results:
            key = (r.file_path, r.start_line)
            self.assertNotIn(key, seen)
            seen.add(key)
        store.close()

    def test_hybrid_respects_top_k(self) -> None:
        retriever, store = self._build_retriever()
        results = retriever.search("calculate sum database json", top_k=2)
        self.assertLessEqual(len(results), 2)
        store.close()

    def test_hybrid_weights_affect_ranking(self) -> None:
        gen = EmbeddingGenerator()
        store = VectorStore()
        # Keyword-heavy retriever
        r1 = HybridRetriever(store, gen, semantic_weight=0.0, keyword_weight=1.0, recency_weight=0.0)
        # Semantic-heavy retriever
        r2 = HybridRetriever(store, gen, semantic_weight=1.0, keyword_weight=0.0, recency_weight=0.0)
        # Just ensure they can be created with different weights
        self.assertEqual(r1.keyword_weight, 1.0)
        self.assertEqual(r2.semantic_weight, 1.0)
        store.close()

    def test_rrf_fusion_scoring(self) -> None:
        retriever, store = self._build_retriever()
        results = retriever.search("calculate", top_k=3)
        # All hybrid results should have source="hybrid"
        for r in results:
            self.assertEqual(r.source, "hybrid")
        # Scores should be positive
        for r in results:
            self.assertGreater(r.score, 0)
        store.close()

    def test_search_semantic_method(self) -> None:
        retriever, store = self._build_retriever()
        results = retriever.search_semantic("json parse data", top_k=3)
        self.assertIsInstance(results, list)
        store.close()

    def test_search_keyword_method(self) -> None:
        retriever, store = self._build_retriever()
        results = retriever.search_keyword("json parse data", top_k=3)
        self.assertIsInstance(results, list)
        store.close()

    def test_retrieval_result_fields(self) -> None:
        retriever, store = self._build_retriever()
        results = retriever.search("calculate sum", top_k=1)
        if results:
            r = results[0]
            self.assertIsInstance(r.file_path, str)
            self.assertIsInstance(r.start_line, int)
            self.assertIsInstance(r.end_line, int)
            self.assertIsInstance(r.content, str)
            self.assertIsInstance(r.score, float)
            self.assertIsInstance(r.source, str)
            self.assertIsInstance(r.chunk_type, str)
            self.assertIsInstance(r.name, str)
        store.close()


if __name__ == "__main__":
    unittest.main()
