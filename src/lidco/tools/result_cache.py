"""Hash-based tool result cache."""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CacheEntry:
    """A single cached tool result."""

    key: str
    tool_name: str
    result: str
    created_at: float = field(default_factory=time.time)
    ttl: float = 300.0
    hit_count: int = 0


class ToolResultCache:
    """LRU-style cache for tool invocation results."""

    def __init__(self, max_size: int = 1000, default_ttl: float = 300.0) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._entries: dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _make_key(self, tool_name: str, args: str) -> str:
        """Return md5 hex digest of *tool_name* + *args*."""
        raw = f"{tool_name}:{args}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _is_expired(self, entry: CacheEntry) -> bool:
        return (time.time() - entry.created_at) > entry.ttl

    def _maybe_evict_oldest(self) -> None:
        """Evict oldest entry when at capacity."""
        if len(self._entries) <= self._max_size:
            return
        oldest_key = min(self._entries, key=lambda k: self._entries[k].created_at)
        del self._entries[oldest_key]
        self._evictions += 1

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, tool_name: str, args: str) -> str | None:
        """Return cached result if present and not expired."""
        key = self._make_key(tool_name, args)
        entry = self._entries.get(key)
        if entry is None or self._is_expired(entry):
            if entry is not None:
                del self._entries[key]
            self._misses += 1
            return None
        # Increment hit_count immutably (frozen dataclass)
        updated = CacheEntry(
            key=entry.key,
            tool_name=entry.tool_name,
            result=entry.result,
            created_at=entry.created_at,
            ttl=entry.ttl,
            hit_count=entry.hit_count + 1,
        )
        self._entries[key] = updated
        self._hits += 1
        return entry.result

    def put(
        self, tool_name: str, args: str, result: str, ttl: float | None = None
    ) -> CacheEntry:
        """Store a tool result in the cache."""
        key = self._make_key(tool_name, args)
        entry = CacheEntry(
            key=key,
            tool_name=tool_name,
            result=result,
            ttl=ttl if ttl is not None else self._default_ttl,
        )
        self._entries[key] = entry
        self._maybe_evict_oldest()
        return entry

    def invalidate(self, tool_name: str, args: str) -> bool:
        """Remove a specific entry. Return True if removed."""
        key = self._make_key(tool_name, args)
        if key in self._entries:
            del self._entries[key]
            return True
        return False

    def invalidate_by_tool(self, tool_name: str) -> int:
        """Remove all entries for *tool_name*. Return count removed."""
        keys = [k for k, e in self._entries.items() if e.tool_name == tool_name]
        for k in keys:
            del self._entries[k]
        return len(keys)

    def evict_expired(self) -> int:
        """Remove all expired entries. Return count removed."""
        now = time.time()
        expired = [
            k for k, e in self._entries.items() if (now - e.created_at) > e.ttl
        ]
        for k in expired:
            del self._entries[k]
        self._evictions += len(expired)
        return len(expired)

    def stats(self) -> dict:
        """Return cache statistics."""
        return {
            "size": len(self._entries),
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
        }

    def clear(self) -> None:
        """Remove all entries."""
        self._entries = {}
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def summary(self) -> str:
        """Human-readable summary."""
        s = self.stats()
        total = s["hits"] + s["misses"]
        rate = (s["hits"] / total * 100) if total else 0.0
        return (
            f"ToolResultCache: {s['size']} entries, "
            f"{s['hits']} hits / {s['misses']} misses ({rate:.1f}% hit rate), "
            f"{s['evictions']} evictions"
        )
