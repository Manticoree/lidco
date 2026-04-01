"""Cache query results with file-change invalidation."""
from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CacheEntry:
    """A single cache entry."""

    query_hash: str
    result: Any
    created_at: float
    file_paths: tuple[str, ...] = ()
    valid: bool = True


class QueryCache:
    """LRU cache for query results with TTL and file-invalidation support."""

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 300.0) -> None:
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def get(self, query_hash: str) -> Any | None:
        """Return cached result or ``None``."""
        entry = self._entries.get(query_hash)
        if entry is None or not entry.valid:
            self._misses += 1
            return None
        if self._is_expired(entry):
            entry.valid = False
            self._misses += 1
            return None
        self._hits += 1
        # move to end (most recent)
        self._entries.move_to_end(query_hash)
        return entry.result

    def put(self, query_hash: str, result: Any, file_paths: tuple[str, ...] = ()) -> None:
        """Store a result in the cache."""
        if query_hash in self._entries:
            self._entries.move_to_end(query_hash)
            self._entries[query_hash] = CacheEntry(
                query_hash=query_hash,
                result=result,
                created_at=time.monotonic(),
                file_paths=file_paths,
            )
            return

        if len(self._entries) >= self._max_size:
            self._entries.popitem(last=False)
            self._evictions += 1

        self._entries[query_hash] = CacheEntry(
            query_hash=query_hash,
            result=result,
            created_at=time.monotonic(),
            file_paths=file_paths,
        )

    def invalidate_file(self, file_path: str) -> int:
        """Invalidate entries referencing *file_path*. Return count."""
        count = 0
        for entry in self._entries.values():
            if entry.valid and file_path in entry.file_paths:
                entry.valid = False
                count += 1
        return count

    def invalidate_all(self) -> int:
        """Invalidate all entries. Return count."""
        count = 0
        for entry in self._entries.values():
            if entry.valid:
                entry.valid = False
                count += 1
        return count

    def evict_expired(self) -> int:
        """Remove expired entries from the cache. Return count."""
        expired = [
            k for k, e in self._entries.items()
            if not e.valid or self._is_expired(e)
        ]
        for k in expired:
            del self._entries[k]
        self._evictions += len(expired)
        return len(expired)

    def stats(self) -> dict[str, int]:
        """Return cache statistics."""
        return {
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "size": len(self._entries),
        }

    def clear(self) -> None:
        """Clear the cache entirely."""
        self._entries.clear()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    def _is_expired(self, entry: CacheEntry) -> bool:
        return (time.monotonic() - entry.created_at) > self._ttl
