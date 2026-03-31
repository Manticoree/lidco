"""Hybrid retrieval combining vector similarity, BM25 keyword, and recency signals."""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass

from lidco.embeddings.vector_store import VectorEntry, VectorStore
from lidco.embeddings.generator import EmbeddingGenerator


_STOPWORDS: frozenset[str] = frozenset(
    {
        "the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to",
        "for", "of", "and", "or", "not", "this", "that", "it", "with", "from",
        "by", "as", "be", "has", "have", "had", "do", "does", "did", "will",
        "would", "can", "could", "should", "may", "might", "shall",
    }
)


@dataclass(frozen=True)
class RetrievalResult:
    """A single retrieval result."""

    file_path: str
    start_line: int
    end_line: int
    content: str
    score: float
    source: str  # "semantic" | "keyword" | "hybrid"
    chunk_type: str
    name: str


class BM25Index:
    """BM25 keyword index."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._docs: dict[str, list[str]] = {}
        self._doc_len: dict[str, int] = {}
        self._avg_dl: float = 0.0
        self._df: dict[str, int] = {}
        self._n: int = 0

    def add_document(self, doc_id: str, text: str) -> None:
        tokens = self._tokenize(text)
        self._docs[doc_id] = tokens
        self._doc_len[doc_id] = len(tokens)
        self._n = len(self._docs)

        # Update avg doc length
        total = sum(self._doc_len.values())
        self._avg_dl = total / max(self._n, 1)

        # Update document frequencies
        seen = set(tokens)
        for token in seen:
            self._df[token] = self._df.get(token, 0) + 1

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        query_tokens = self._tokenize(query)
        if not query_tokens or not self._docs:
            return []

        scores: dict[str, float] = {}
        for doc_id, doc_tokens in self._docs.items():
            score = self._score_doc(query_tokens, doc_id, doc_tokens)
            if score > 0:
                scores[doc_id] = score

        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_results[:top_k]

    def _score_doc(
        self, query_tokens: list[str], doc_id: str, doc_tokens: list[str]
    ) -> float:
        dl = self._doc_len[doc_id]
        score = 0.0

        # Build term frequency map for this doc
        tf_map: dict[str, int] = {}
        for t in doc_tokens:
            tf_map[t] = tf_map.get(t, 0) + 1

        for qt in query_tokens:
            if qt not in tf_map:
                continue
            tf = tf_map[qt]
            df = self._df.get(qt, 0)
            idf = math.log((self._n - df + 0.5) / (df + 0.5) + 1)
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (
                1 - self.b + self.b * dl / max(self._avg_dl, 1)
            )
            score += idf * numerator / denominator

        return score

    def _tokenize(self, text: str) -> list[str]:
        raw = re.findall(r"[a-zA-Z0-9]+", text.lower())
        return [t for t in raw if t not in _STOPWORDS and len(t) > 1]

    def clear(self) -> None:
        self._docs.clear()
        self._doc_len.clear()
        self._df.clear()
        self._avg_dl = 0.0
        self._n = 0


class HybridRetriever:
    """Hybrid retriever combining semantic, keyword, and recency signals."""

    def __init__(
        self,
        vector_store: VectorStore,
        generator: EmbeddingGenerator,
        semantic_weight: float = 0.5,
        keyword_weight: float = 0.3,
        recency_weight: float = 0.2,
    ) -> None:
        self.vector_store = vector_store
        self.generator = generator
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.recency_weight = recency_weight
        self._bm25 = BM25Index()
        self._entries: dict[str, VectorEntry] = {}

    def build_keyword_index(self, entries: list[VectorEntry]) -> None:
        self._bm25.clear()
        self._entries.clear()
        for entry in entries:
            self._bm25.add_document(entry.id, entry.content)
            self._entries[entry.id] = entry

    def search(self, query: str, top_k: int = 10) -> list[RetrievalResult]:
        """Hybrid search using RRF fusion."""
        # 1. Semantic search
        sem_results = self._semantic_search_raw(query, top_k=top_k * 2)
        # 2. Keyword search
        kw_results = self._keyword_search_raw(query, top_k=top_k * 2)
        # 3. Recency ranking
        rec_results = self._recency_ranking(top_k=top_k * 2)

        # RRF fusion (k=60)
        k = 60
        rrf_scores: dict[str, float] = {}
        id_to_entry: dict[str, VectorEntry] = {}

        for rank, (entry, _score) in enumerate(sem_results):
            rrf_scores[entry.id] = rrf_scores.get(entry.id, 0) + self.semantic_weight / (k + rank + 1)
            id_to_entry[entry.id] = entry

        for rank, (entry, _score) in enumerate(kw_results):
            rrf_scores[entry.id] = rrf_scores.get(entry.id, 0) + self.keyword_weight / (k + rank + 1)
            id_to_entry[entry.id] = entry

        for rank, (entry, _score) in enumerate(rec_results):
            rrf_scores[entry.id] = rrf_scores.get(entry.id, 0) + self.recency_weight / (k + rank + 1)
            id_to_entry[entry.id] = entry

        # Deduplicate by (file_path, start_line)
        seen: set[tuple[str, int]] = set()
        deduped: list[tuple[str, float]] = []
        for eid, score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True):
            entry = id_to_entry[eid]
            key = (entry.file_path, entry.start_line)
            if key not in seen:
                seen.add(key)
                deduped.append((eid, score))

        results: list[RetrievalResult] = []
        for eid, score in deduped[:top_k]:
            entry = id_to_entry[eid]
            results.append(
                RetrievalResult(
                    file_path=entry.file_path,
                    start_line=entry.start_line,
                    end_line=entry.end_line,
                    content=entry.content,
                    score=score,
                    source="hybrid",
                    chunk_type=entry.chunk_type,
                    name=entry.name,
                )
            )
        return results

    def search_semantic(self, query: str, top_k: int = 10) -> list[RetrievalResult]:
        raw = self._semantic_search_raw(query, top_k)
        return [
            RetrievalResult(
                file_path=e.file_path,
                start_line=e.start_line,
                end_line=e.end_line,
                content=e.content,
                score=s,
                source="semantic",
                chunk_type=e.chunk_type,
                name=e.name,
            )
            for e, s in raw
        ]

    def search_keyword(self, query: str, top_k: int = 10) -> list[RetrievalResult]:
        raw = self._keyword_search_raw(query, top_k)
        return [
            RetrievalResult(
                file_path=e.file_path,
                start_line=e.start_line,
                end_line=e.end_line,
                content=e.content,
                score=s,
                source="keyword",
                chunk_type=e.chunk_type,
                name=e.name,
            )
            for e, s in raw
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _semantic_search_raw(
        self, query: str, top_k: int
    ) -> list[tuple[VectorEntry, float]]:
        emb = self.generator.generate_embedding(query)
        return self.vector_store.search(emb, top_k=top_k)

    def _keyword_search_raw(
        self, query: str, top_k: int
    ) -> list[tuple[VectorEntry, float]]:
        bm25_results = self._bm25.search(query, top_k=top_k)
        results: list[tuple[VectorEntry, float]] = []
        for doc_id, score in bm25_results:
            if doc_id in self._entries:
                results.append((self._entries[doc_id], score))
        return results

    def _recency_ranking(
        self, top_k: int
    ) -> list[tuple[VectorEntry, float]]:
        if not self._entries:
            return []
        entries = list(self._entries.values())
        # Sort by updated_at descending, assign rank-based scores
        entries.sort(key=lambda e: e.updated_at, reverse=True)
        results: list[tuple[VectorEntry, float]] = []
        for i, entry in enumerate(entries[:top_k]):
            score = 1.0 / (i + 1)  # rank-based score
            results.append((entry, score))
        return results
