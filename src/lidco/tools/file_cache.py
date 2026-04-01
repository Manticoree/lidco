"""Cache file contents by path + mtime."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FileCacheEntry:
    """Cached file content."""

    path: str
    content: str
    mtime: float = 0.0
    size: int = 0
    cached_at: float = field(default_factory=time.time)


class FileReadCache:
    """LRU-like cache for file reads keyed by path + mtime."""

    def __init__(self, max_entries: int = 500) -> None:
        self._max_entries = max_entries
        self._entries: dict[str, FileCacheEntry] = {}
        self._hits = 0
        self._misses = 0

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _maybe_evict(self) -> None:
        while len(self._entries) > self._max_entries:
            oldest = min(self._entries, key=lambda k: self._entries[k].cached_at)
            del self._entries[oldest]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, path: str, current_mtime: float = 0.0) -> str | None:
        """Return cached content if mtime matches (0.0 = always hit)."""
        entry = self._entries.get(path)
        if entry is None:
            self._misses += 1
            return None
        # If caller passes 0.0, skip mtime check (always hit)
        if current_mtime != 0.0 and entry.mtime != current_mtime:
            self._misses += 1
            return None
        self._hits += 1
        return entry.content

    def put(self, path: str, content: str, mtime: float = 0.0) -> FileCacheEntry:
        """Cache file content for *path*."""
        entry = FileCacheEntry(
            path=path,
            content=content,
            mtime=mtime,
            size=len(content),
        )
        self._entries[path] = entry
        self._maybe_evict()
        return entry

    def invalidate(self, path: str) -> bool:
        """Remove a specific cached file. Return True if removed."""
        if path in self._entries:
            del self._entries[path]
            return True
        return False

    def invalidate_by_prefix(self, prefix: str) -> int:
        """Remove all entries whose path starts with *prefix*."""
        keys = [k for k in self._entries if k.startswith(prefix)]
        for k in keys:
            del self._entries[k]
        return len(keys)

    def preload(self, paths: list[str], contents: dict[str, str]) -> int:
        """Bulk load paths from *contents* dict. Return count loaded."""
        loaded = 0
        for p in paths:
            if p in contents:
                self.put(p, contents[p])
                loaded += 1
        return loaded

    def stats(self) -> dict:
        """Return cache statistics."""
        return {
            "entries": len(self._entries),
            "hits": self._hits,
            "misses": self._misses,
        }

    def clear(self) -> None:
        """Remove all entries."""
        self._entries = {}
        self._hits = 0
        self._misses = 0

    def summary(self) -> str:
        """Human-readable summary."""
        s = self.stats()
        total = s["hits"] + s["misses"]
        rate = (s["hits"] / total * 100) if total else 0.0
        return (
            f"FileReadCache: {s['entries']} entries, "
            f"{s['hits']} hits / {s['misses']} misses ({rate:.1f}% hit rate)"
        )
