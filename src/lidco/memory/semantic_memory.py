"""Semantic memory store with priority levels and TTL-based expiry.

Extends basic memory with:
- TF-IDF cosine similarity search (stdlib-only, no numpy/sklearn)
- Priority levels (1–5, higher = more important)
- TTL expiry (entries older than their TTL are excluded from search)
- JSON persistence
"""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# TF-IDF helpers (stdlib-only)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())


def _tf(tokens: list[str]) -> dict[str, float]:
    if not tokens:
        return {}
    counts: dict[str, int] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    total = len(tokens)
    return {t: c / total for t, c in counts.items()}


def _idf(term: str, docs: list[list[str]]) -> float:
    n = len(docs)
    df = sum(1 for d in docs if term in d)
    return math.log(1 + n / (1 + df))


def _tfidf_vector(tokens: list[str], docs: list[list[str]]) -> dict[str, float]:
    tf = _tf(tokens)
    return {t: tf_val * _idf(t, docs) for t, tf_val in tf.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    common = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in common)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class MemoryEntry:
    key: str
    content: str
    tags: list[str] = field(default_factory=list)
    priority: int = 3          # 1 (low) … 5 (high)
    ttl: float = 0.0           # seconds; 0 = never expires
    created_at: float = field(default_factory=time.time)
    access_count: int = 0

    def is_expired(self) -> bool:
        if self.ttl <= 0:
            return False
        return time.time() - self.created_at > self.ttl

    def score_boost(self) -> float:
        """Priority multiplier applied on top of cosine similarity."""
        return 0.5 + (self.priority - 1) * 0.125  # 0.5 … 1.0


@dataclass
class SearchResult:
    entry: MemoryEntry
    score: float


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class SemanticMemoryStore:
    """Semantic memory store with priority + TTL + cosine search.

    Parameters
    ----------
    store_path:
        Optional JSON file for persistence. If None, store lives in memory only.
    max_entries:
        Hard cap on total entries (LRU eviction when exceeded).
    """

    def __init__(
        self,
        store_path: str | Path | None = None,
        max_entries: int = 1000,
        enabled: bool = True,
    ) -> None:
        self._store_path = Path(store_path) if store_path else None
        self._max = max_entries
        self._enabled = enabled
        self._entries: dict[str, MemoryEntry] = {}
        if self._store_path and self._store_path.exists():
            self._load()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(
        self,
        key: str,
        content: str,
        tags: list[str] | None = None,
        priority: int = 3,
        ttl: float = 0.0,
    ) -> MemoryEntry:
        entry = MemoryEntry(
            key=key,
            content=content,
            tags=tags or [],
            priority=max(1, min(5, priority)),
            ttl=ttl,
        )
        if not self._enabled:
            return entry
        self._entries[key] = entry
        self._evict_if_needed()
        return entry

    def get(self, key: str) -> MemoryEntry | None:
        entry = self._entries.get(key)
        if entry and entry.is_expired():
            del self._entries[key]
            return None
        if entry:
            entry.access_count += 1
        return entry

    def delete(self, key: str) -> bool:
        return self._entries.pop(key, None) is not None

    def update_priority(self, key: str, priority: int) -> bool:
        entry = self._entries.get(key)
        if not entry:
            return False
        entry.priority = max(1, min(5, priority))
        return True

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
        tags: list[str] | None = None,
        min_priority: int = 1,
    ) -> list[SearchResult]:
        """Find the most semantically similar non-expired entries."""
        if not self._enabled:
            return []
        # Filter candidates
        candidates = [
            e for e in self._entries.values()
            if not e.is_expired() and e.priority >= min_priority
        ]
        if tags:
            tag_set = set(tags)
            candidates = [e for e in candidates if tag_set & set(e.tags)]

        if not candidates:
            return []

        # Build corpus for IDF
        all_tokens = [_tokenize(e.content + " " + " ".join(e.tags)) for e in candidates]
        query_tokens = _tokenize(query)
        query_vec = _tfidf_vector(query_tokens, all_tokens)

        results: list[SearchResult] = []
        for entry, tokens in zip(candidates, all_tokens):
            doc_vec = _tfidf_vector(tokens, all_tokens)
            sim = _cosine(query_vec, doc_vec) * entry.score_boost()
            if sim >= min_score:
                results.append(SearchResult(entry=entry, score=sim))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    def purge_expired(self) -> int:
        expired = [k for k, e in self._entries.items() if e.is_expired()]
        for k in expired:
            del self._entries[k]
        return len(expired)

    def all_entries(self) -> list[MemoryEntry]:
        return [e for e in self._entries.values() if not e.is_expired()]

    def stats(self) -> dict[str, Any]:
        alive = self.all_entries()
        return {
            "total": len(alive),
            "by_priority": {
                str(p): sum(1 for e in alive if e.priority == p)
                for p in range(1, 6)
            },
            "with_ttl": sum(1 for e in alive if e.ttl > 0),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str | Path | None = None) -> None:
        target = Path(path) if path else self._store_path
        if not target:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        data = {k: asdict(v) for k, v in self._entries.items()}
        target.write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        try:
            data = json.loads(self._store_path.read_text())  # type: ignore[union-attr]
            for k, v in data.items():
                self._entries[k] = MemoryEntry(**v)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _evict_if_needed(self) -> None:
        """Evict lowest-priority, oldest entries when over capacity."""
        while len(self._entries) > self._max:
            # Sort by (priority asc, created_at asc) → evict worst
            victim = min(
                self._entries.values(),
                key=lambda e: (e.priority, e.created_at),
            )
            del self._entries[victim.key]
