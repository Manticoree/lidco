"""Prompt Cache — LRU prompt cache with TTL, stats, and eviction."""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class CacheEntry:
    """A single cached prompt entry."""

    key: str
    value: str
    created_at: float
    ttl: float


@dataclass(frozen=True)
class CacheStats:
    """Cache performance statistics."""

    hits: int
    misses: int
    evictions: int
    size: int


class PromptCache:
    """LRU prompt cache with per-key TTL.

    Parameters
    ----------
    max_size:
        Maximum number of entries before eviction.
    default_ttl:
        Default time-to-live in seconds.
    """

    def __init__(self, max_size: int = 1000, default_ttl: float = 3600.0) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._data: dict[str, CacheEntry] = {}
        self._access_order: list[str] = []
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str) -> str | None:
        """Return cached value or None if missing/expired."""
        entry = self._data.get(key)
        if entry is None:
            self._misses += 1
            return None
        if time.monotonic() - entry.created_at > entry.ttl:
            del self._data[key]
            if key in self._access_order:
                self._access_order.remove(key)
            self._misses += 1
            return None
        # Move to end (most-recently-used)
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
        self._hits += 1
        return entry.value

    def put(self, key: str, value: str, ttl: float | None = None) -> None:
        """Store *key* -> *value*.  Evicts LRU if at capacity."""
        effective_ttl = ttl if ttl is not None else self._default_ttl
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=time.monotonic(),
            ttl=effective_ttl,
        )
        if key in self._data:
            if key in self._access_order:
                self._access_order.remove(key)
        self._data[key] = entry
        self._access_order.append(key)
        while len(self._data) > self._max_size:
            oldest_key = self._access_order.pop(0)
            if oldest_key in self._data:
                del self._data[oldest_key]
                self._evictions += 1

    def evict(self, key: str) -> bool:
        """Remove *key*. Return True if it existed."""
        if key in self._data:
            del self._data[key]
            if key in self._access_order:
                self._access_order.remove(key)
            return True
        return False

    @property
    def stats(self) -> CacheStats:
        """Current cache statistics."""
        return CacheStats(
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
            size=len(self._data),
        )

    def clear(self) -> None:
        """Remove all entries."""
        self._data.clear()
        self._access_order.clear()


__all__ = ["CacheEntry", "CacheStats", "PromptCache"]
