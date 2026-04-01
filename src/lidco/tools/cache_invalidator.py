"""Watch file changes and invalidate affected cache entries."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class InvalidationEvent:
    """Record of a cache invalidation triggered by a file change."""

    path: str
    reason: str = "file_changed"
    timestamp: float = field(default_factory=time.time)
    affected_keys: tuple[str, ...] = ()


class CacheInvalidator:
    """Map file paths to cache keys and produce invalidation events."""

    def __init__(self) -> None:
        self._watchers: dict[str, set[str]] = {}
        self._events: list[InvalidationEvent] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def watch(self, path: str, cache_keys: list[str]) -> None:
        """Register *cache_keys* to be invalidated when *path* changes."""
        existing = self._watchers.get(path, set())
        self._watchers[path] = existing | set(cache_keys)

    def unwatch(self, path: str) -> bool:
        """Remove all watchers for *path*. Return True if path was watched."""
        if path in self._watchers:
            del self._watchers[path]
            return True
        return False

    def on_file_changed(self, path: str) -> InvalidationEvent:
        """Create an invalidation event for *path*."""
        keys = tuple(sorted(self._watchers.get(path, set())))
        event = InvalidationEvent(
            path=path,
            reason="file_changed",
            affected_keys=keys,
        )
        self._events = [*self._events, event]
        return event

    def get_affected_keys(self, path: str) -> list[str]:
        """Return cache keys associated with *path*."""
        return sorted(self._watchers.get(path, set()))

    def batch_invalidate(self, paths: list[str]) -> list[InvalidationEvent]:
        """Create invalidation events for multiple *paths*."""
        events: list[InvalidationEvent] = []
        for p in paths:
            events.append(self.on_file_changed(p))
        return events

    def get_events(self, limit: int = 50) -> list[InvalidationEvent]:
        """Return the last *limit* invalidation events."""
        return self._events[-limit:]

    def clear(self) -> None:
        """Remove all watchers and events."""
        self._watchers = {}
        self._events = []

    def summary(self) -> str:
        """Human-readable summary."""
        total_keys = sum(len(v) for v in self._watchers.values())
        return (
            f"CacheInvalidator: {len(self._watchers)} watched paths, "
            f"{total_keys} cache keys, {len(self._events)} events"
        )
