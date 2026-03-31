"""LRUCache — LRU eviction with per-key TTL (stdlib only)."""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

_UNSET = object()


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0


class _CacheEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, expires_at: float | None) -> None:
        self.value = value
        self.expires_at = expires_at

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.monotonic() > self.expires_at


class LRUCache:
    """
    LRU cache with optional per-key TTL.

    Parameters
    ----------
    maxsize:
        Maximum number of entries.  Must be >= 1.
    ttl:
        Default time-to-live in seconds for new entries.  *None* = no expiry.
    """

    def __init__(self, maxsize: int = 128, ttl: float | None = None) -> None:
        if maxsize < 1:
            raise ValueError(f"maxsize must be >= 1, got {maxsize}")
        self._maxsize = maxsize
        self._default_ttl = ttl
        self._data: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ public

    def get(self, key: str, default: Any = None) -> Any:
        """Return value for *key*, or *default* if missing/expired."""
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._misses += 1
                return default
            if entry.is_expired():
                del self._data[key]
                self._misses += 1
                return default
            # Move to end (most-recently-used)
            self._data.move_to_end(key)
            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: Any = _UNSET) -> None:
        """
        Store *key* → *value*.

        Parameters
        ----------
        ttl:
            Per-key TTL override.  Pass explicit *None* for no expiry.
            Omit to use the cache-level default.
        """
        with self._lock:
            if ttl is _UNSET:
                effective_ttl = self._default_ttl
            else:
                effective_ttl = ttl

            expires_at = (time.monotonic() + effective_ttl) if effective_ttl is not None else None
            entry = _CacheEntry(value=value, expires_at=expires_at)

            if key in self._data:
                self._data.move_to_end(key)
                self._data[key] = entry
            else:
                self._data[key] = entry
                if len(self._data) > self._maxsize:
                    # Evict the oldest (leftmost) entry
                    self._data.popitem(last=False)
                    self._evictions += 1

    def put(self, key: str, value: Any, ttl: Any = _UNSET) -> None:
        """Alias for :meth:`set`."""
        self.set(key, value, ttl)

    def evict(self, key: str) -> bool:
        """Remove *key*.  Return True if it existed."""
        with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False

    def delete(self, key: str) -> bool:
        """Alias for :meth:`evict`."""
        return self.evict(key)

    def clear(self) -> None:
        """Remove all entries."""
        with self._lock:
            self._data.clear()

    def keys(self) -> list[str]:
        """Return all non-expired keys."""
        expired = [k for k, e in list(self._data.items()) if e.is_expired()]
        for k in expired:
            del self._data[k]
        return list(self._data.keys())

    def stats(self) -> CacheStats:
        return CacheStats(
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
            size=len(self._data),
        )

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: object) -> bool:
        entry = self._data.get(str(key))  # type: ignore[arg-type]
        if entry is None:
            return False
        if entry.is_expired():
            del self._data[str(key)]  # type: ignore[arg-type]
            return False
        return True
