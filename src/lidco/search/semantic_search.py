"""TF-IDF semantic code search — no numpy/sklearn, pure Python (Copilot semantic search parity)."""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SearchDocument:
    id: str           # unique identifier (file path or symbol name)
    text: str         # searchable text content
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    doc: SearchDocument
    score: float      # 0.0–1.0 cosine similarity

    def __repr__(self) -> str:
        return f"SearchResult({self.doc.id!r}, score={self.score:.3f})"


def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase, split on non-alphanumeric, keep identifiers."""
    # Split camelCase and snake_case
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    tokens = re.findall(r'[a-zA-Z_]\w*', text.lower())
    return [t for t in tokens if len(t) > 1]


def _tf(tokens: list[str]) -> dict[str, float]:
    if not tokens:
        return {}
    counts = Counter(tokens)
    total = len(tokens)
    return {t: c / total for t, c in counts.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    shared = set(a) & set(b)
    if not shared:
        return 0.0
    dot = sum(a[t] * b[t] for t in shared)
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class SemanticSearch:
    """TF-IDF + cosine similarity search over a corpus of code documents.

    Supports indexing Python files or arbitrary text documents.
    """

    def __init__(self) -> None:
        self._docs: list[SearchDocument] = []
        self._tfs: list[dict[str, float]] = []
        self._idf: dict[str, float] = {}
        self._built = False

    def add(self, doc: SearchDocument) -> None:
        self._docs.append(doc)
        self._tfs.append(_tf(_tokenize(doc.text)))
        self._built = False

    def add_file(self, path: str | Path, metadata: dict[str, Any] | None = None) -> bool:
        p = Path(path)
        if not p.exists():
            return False
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            self.add(SearchDocument(id=str(p), text=text, metadata=metadata or {}))
            return True
        except OSError:
            return False

    def index_directory(self, root: str | Path, extensions: list[str] | None = None) -> int:
        root = Path(root)
        exts = set(extensions or [".py"])
        skip = {".git", "__pycache__", ".venv", "venv", "dist", "build"}
        count = 0
        for p in root.rglob("*"):
            if p.suffix in exts and not any(s in p.parts for s in skip):
                if self.add_file(p):
                    count += 1
        return count

    def _build_idf(self) -> None:
        n = len(self._docs)
        if n == 0:
            return
        df: dict[str, int] = defaultdict(int)
        for tf in self._tfs:
            for term in tf:
                df[term] += 1
        self._idf = {term: math.log(1 + n / (1 + count)) for term, count in df.items()}
        self._built = True

    def _tfidf(self, tf: dict[str, float]) -> dict[str, float]:
        return {t: v * self._idf.get(t, 0.0) for t, v in tf.items()}

    def search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        """Return top_k most similar documents for query."""
        if not self._built:
            self._build_idf()
        if not self._docs:
            return []
        query_tf = _tf(_tokenize(query))
        query_tfidf = self._tfidf(query_tf)
        results: list[SearchResult] = []
        for doc, tf in zip(self._docs, self._tfs):
            doc_tfidf = self._tfidf(tf)
            score = _cosine(query_tfidf, doc_tfidf)
            if score > 0:
                results.append(SearchResult(doc=doc, score=score))
        return sorted(results, key=lambda r: -r.score)[:top_k]

    def search_code(self, query: str, top_k: int = 5) -> str:
        """Human-readable search results."""
        results = self.search(query, top_k)
        if not results:
            return f"No results for: {query!r}"
        lines = [f"Top {len(results)} result(s) for {query!r}:"]
        for r in results:
            name = Path(r.doc.id).name if "/" in r.doc.id or "\\" in r.doc.id else r.doc.id
            lines.append(f"  [{r.score:.2f}] {name}")
        return "\n".join(lines)

    @property
    def doc_count(self) -> int:
        return len(self._docs)
