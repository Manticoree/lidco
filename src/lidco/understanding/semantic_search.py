"""TF-IDF based semantic code search."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SearchScope(str, Enum):
    """Scope of a search result."""

    FILE = "file"
    SYMBOL = "symbol"
    SNIPPET = "snippet"


@dataclass(frozen=True)
class SearchResult:
    """A single search result."""

    path: str
    name: str
    score: float
    snippet: str = ""
    line: int = 0
    scope: SearchScope = SearchScope.SYMBOL


_STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "is", "it", "by", "as", "if", "be", "do", "no", "so", "up",
        "with", "from", "that", "this", "not", "are", "was", "has", "have",
        "will", "can", "all", "its", "been", "were", "had", "did", "get",
    }
)


class SemanticSearchIndex:
    """TF-IDF based semantic search index for code."""

    def __init__(self) -> None:
        self._documents: dict[str, dict[str, Any]] = {}
        self._idf_dirty: bool = True
        self._idf_cache: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_document(
        self,
        path: str,
        name: str,
        content: str,
        scope: SearchScope = SearchScope.SYMBOL,
    ) -> None:
        """Add a document to the index."""
        tokens = self._tokenize(content)
        self._documents[path] = {
            "name": name,
            "content": content,
            "scope": scope,
            "tokens": tokens,
        }
        self._idf_dirty = True

    def search(
        self,
        query: str,
        top_k: int = 10,
        scope: SearchScope | None = None,
    ) -> list[SearchResult]:
        """Search for documents matching *query*."""
        if not self._documents:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        self._rebuild_idf()
        query_tfidf = self._compute_tfidf(query_tokens)

        scored: list[tuple[float, str]] = []
        for path, doc in self._documents.items():
            if scope is not None and doc["scope"] != scope:
                continue
            doc_tfidf = self._compute_tfidf(doc["tokens"])
            score = self._cosine(query_tfidf, doc_tfidf)
            if score > 0.0:
                scored.append((score, path))

        scored.sort(key=lambda t: t[0], reverse=True)

        results: list[SearchResult] = []
        for score, path in scored[:top_k]:
            doc = self._documents[path]
            snippet = doc["content"][:200]
            results.append(
                SearchResult(
                    path=path,
                    name=doc["name"],
                    score=round(score, 6),
                    snippet=snippet,
                    scope=doc["scope"],
                )
            )
        return results

    def document_count(self) -> int:
        """Return number of indexed documents."""
        return len(self._documents)

    def clear(self) -> None:
        """Remove all documents from the index."""
        self._documents.clear()
        self._idf_dirty = True
        self._idf_cache.clear()

    def remove_document(self, path: str) -> bool:
        """Remove a document by path. Returns True if it existed."""
        if path in self._documents:
            del self._documents[path]
            self._idf_dirty = True
            return True
        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _tokenize(self, text: str) -> list[str]:
        """Lowercase split, filter stopwords and short tokens."""
        raw = text.lower().split()
        return [t for t in raw if t not in _STOPWORDS and len(t) > 1]

    def _compute_tfidf(self, tokens: list[str]) -> dict[str, float]:
        """Compute TF-IDF vector for a token list."""
        if not tokens:
            return {}
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1

        total = len(tokens)
        result: dict[str, float] = {}
        for term, count in tf.items():
            idf = self._idf_cache.get(term, 1.0)
            result[term] = (count / total) * idf
        return result

    def _rebuild_idf(self) -> None:
        if not self._idf_dirty:
            return
        n = len(self._documents)
        if n == 0:
            self._idf_cache.clear()
            self._idf_dirty = False
            return

        df: dict[str, int] = {}
        for doc in self._documents.values():
            seen: set[str] = set()
            for t in doc["tokens"]:
                if t not in seen:
                    df[t] = df.get(t, 0) + 1
                    seen.add(t)

        self._idf_cache = {
            term: math.log((n + 1) / (freq + 1)) + 1.0
            for term, freq in df.items()
        }
        self._idf_dirty = False

    @staticmethod
    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        """Cosine similarity between two sparse vectors."""
        if not a or not b:
            return 0.0
        common = set(a) & set(b)
        if not common:
            return 0.0
        dot = sum(a[k] * b[k] for k in common)
        mag_a = math.sqrt(sum(v * v for v in a.values()))
        mag_b = math.sqrt(sum(v * v for v in b.values()))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)
