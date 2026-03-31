"""Completion result cache with TTL and LRU eviction."""
from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass, field


@dataclass
class CacheEntry:
    """A cached completion result."""

    prefix: str
    results: list[str]
    timestamp: float
    hit_count: int = 0


class CompletionCache:
    """LRU cache for completion results with TTL expiry."""

    def __init__(self, max_size: int = 200, ttl: float = 300.0) -> None:
        self._max_size = max_size
        self._ttl = ttl
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, prefix: str) -> list[str] | None:
        """Return cached results for *prefix*, or ``None`` on miss."""
        entry = self._entries.get(prefix)
        if entry is None:
            self._misses += 1
            return None
        # Check TTL
        if time.monotonic() - entry.timestamp > self._ttl:
            del self._entries[prefix]
            self._misses += 1
            return None
        # Move to end (most recently used)
        self._entries.move_to_end(prefix)
        entry.hit_count += 1
        self._hits += 1
        return list(entry.results)

    def put(self, prefix: str, results: list[str]) -> None:
        """Store *results* for *prefix*."""
        if prefix in self._entries:
            self._entries.move_to_end(prefix)
            existing = self._entries[prefix]
            existing.results = list(results)
            existing.timestamp = time.monotonic()
            return
        if len(self._entries) >= self._max_size:
            self._entries.popitem(last=False)
        self._entries[prefix] = CacheEntry(
            prefix=prefix,
            results=list(results),
            timestamp=time.monotonic(),
        )

    def invalidate(self, prefix: str | None = None) -> None:
        """Invalidate a specific *prefix* or all entries if ``None``."""
        if prefix is None:
            self._entries.clear()
        else:
            self._entries.pop(prefix, None)

    def stats(self) -> dict[str, object]:
        """Return cache statistics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 4) if total > 0 else 0.0,
            "size": len(self._entries),
        }

    def evict_expired(self) -> int:
        """Remove stale entries.  Returns number evicted."""
        now = time.monotonic()
        expired = [
            k for k, e in self._entries.items() if now - e.timestamp > self._ttl
        ]
        for k in expired:
            del self._entries[k]
        return len(expired)

    def warm(self, items: list[tuple[str, list[str]]]) -> None:
        """Pre-populate cache with *items* (list of (prefix, results) tuples)."""
        for prefix, results in items:
            self.put(prefix, results)
