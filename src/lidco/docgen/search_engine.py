"""Documentation Search Engine — TF-IDF based full-text search (stdlib only).

Indexes documentation strings and allows keyword search with relevance
scoring based on term frequency / inverse document frequency.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SearchResult:
    """A single search result."""

    title: str
    snippet: str
    score: float
    source: str = ""


@dataclass
class _Document:
    title: str
    content: str
    source: str
    terms: dict[str, int] = field(default_factory=dict)


class DocSearchEngine:
    """TF-IDF based documentation search engine."""

    def __init__(self) -> None:
        self._docs: list[_Document] = []
        self._df: dict[str, int] = {}  # document frequency per term

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def index(self, title: str, content: str, source: str = "") -> None:
        """Add a document to the index."""
        terms = _tokenize(title + " " + content)
        tf: dict[str, int] = {}
        for t in terms:
            tf[t] = tf.get(t, 0) + 1

        doc = _Document(title=title, content=content, source=source, terms=tf)
        self._docs.append(doc)

        # Update document frequency
        for t in tf:
            self._df[t] = self._df.get(t, 0) + 1

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Search indexed documents and return ranked results."""
        query_terms = _tokenize(query)
        if not query_terms or not self._docs:
            return []

        n = len(self._docs)
        scored: list[tuple[float, _Document]] = []

        for doc in self._docs:
            score = 0.0
            for qt in query_terms:
                tf = doc.terms.get(qt, 0)
                if tf == 0:
                    continue
                df = self._df.get(qt, 1)
                idf = math.log(n / df) + 1.0
                # Normalized TF
                max_tf = max(doc.terms.values()) if doc.terms else 1
                ntf = tf / max_tf
                score += ntf * idf
            if score > 0:
                scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)

        results: list[SearchResult] = []
        for score, doc in scored[:limit]:
            snippet = _make_snippet(doc.content, query_terms)
            results.append(SearchResult(
                title=doc.title,
                snippet=snippet,
                score=round(score, 4),
                source=doc.source,
            ))
        return results

    def clear(self) -> None:
        """Remove all indexed documents."""
        self._docs = []
        self._df = {}

    def stats(self) -> dict:
        """Return index statistics."""
        return {
            "indexed_count": len(self._docs),
            "total_terms": len(self._df),
        }


# ------------------------------------------------------------------ #
# Internal helpers                                                     #
# ------------------------------------------------------------------ #

_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "it", "in", "on", "of", "to", "and", "or",
    "for", "with", "as", "by", "at", "from", "this", "that", "are", "was",
    "be", "has", "have", "not", "but", "if", "do", "no", "so",
})


def _tokenize(text: str) -> list[str]:
    """Lowercase, split, remove stop words."""
    words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 1]


def _make_snippet(content: str, query_terms: list[str], max_len: int = 200) -> str:
    """Extract a snippet around the first matching term."""
    lower = content.lower()
    best_pos = -1
    for qt in query_terms:
        pos = lower.find(qt)
        if pos >= 0:
            best_pos = pos
            break

    if best_pos < 0:
        return content[:max_len].strip()

    start = max(0, best_pos - 50)
    end = min(len(content), start + max_len)
    snippet = content[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."
    return snippet
