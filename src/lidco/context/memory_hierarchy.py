"""Multi-level memory hierarchy — Task 309.

Provides a four-level memory system:

    session > project > user > org

More specific levels override more general ones.  Each level stores
key→value entries.  Lookups cascade from session down to org.

Usage::

    hierarchy = MemoryHierarchy()
    hierarchy.set("api_key", "sk-...", level="session")
    hierarchy.set("style", "pep8",    level="project")
    hierarchy.set("style", "google",  level="user")     # overridden by project

    value = hierarchy.get("style")   # → "pep8" (project wins)
    value = hierarchy.get("style", max_level="user")  # → "google"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


LEVELS = ("session", "project", "user", "org")
_LEVEL_RANK: dict[str, int] = {level: i for i, level in enumerate(LEVELS)}


@dataclass
class MemoryEntry:
    """A single memory entry in the hierarchy."""

    key: str
    value: Any
    level: str
    tags: list[str] = field(default_factory=list)
    description: str = ""


class MemoryHierarchy:
    """Four-level cascading memory store.

    Lookup order: session (most specific) → project → user → org (least).
    """

    def __init__(self) -> None:
        self._store: dict[str, dict[str, MemoryEntry]] = {
            level: {} for level in LEVELS
        }

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def set(
        self,
        key: str,
        value: Any,
        level: str = "session",
        tags: list[str] | None = None,
        description: str = "",
    ) -> None:
        """Set a key in the given level.

        Raises:
            ValueError: if level is unknown.
        """
        if level not in _LEVEL_RANK:
            raise ValueError(f"Unknown memory level '{level}'. Valid: {LEVELS}")
        self._store[level][key] = MemoryEntry(
            key=key,
            value=value,
            level=level,
            tags=list(tags or []),
            description=description,
        )

    def delete(self, key: str, level: str | None = None) -> bool:
        """Delete a key from a specific level, or from all levels."""
        if level is not None:
            if key in self._store.get(level, {}):
                del self._store[level][key]
                return True
            return False
        removed = False
        for lvl in LEVELS:
            if key in self._store[lvl]:
                del self._store[lvl][key]
                removed = True
        return removed

    def clear(self, level: str | None = None) -> None:
        """Clear all entries at a level, or all levels."""
        if level is not None:
            self._store[level].clear()
        else:
            for lvl in LEVELS:
                self._store[lvl].clear()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None, max_level: str | None = None) -> Any:
        """Return the value for *key* from the most specific level that has it.

        Args:
            key: The key to look up.
            default: Value to return if key not found.
            max_level: Least-specific level to start from (e.g. "user" skips
                "session" and "project" and searches user → org only).
                If None, search from "session" (most specific) down to "org".
        """
        start_rank = _LEVEL_RANK.get(max_level, 0) if max_level else 0
        for rank, level in enumerate(LEVELS):
            if rank < start_rank:
                continue
            if key in self._store[level]:
                return self._store[level][key].value
        return default

    def get_entry(self, key: str, max_level: str | None = None) -> MemoryEntry | None:
        """Return the full MemoryEntry for *key*, or None."""
        start_rank = _LEVEL_RANK.get(max_level, 0) if max_level else 0
        for rank, level in enumerate(LEVELS):
            if rank < start_rank:
                continue
            if key in self._store[level]:
                return self._store[level][key]
        return None

    def get_at_level(self, key: str, level: str) -> Any:
        """Return value at an exact level (no cascading)."""
        entry = self._store.get(level, {}).get(key)
        return entry.value if entry else None

    def list_keys(self, level: str | None = None) -> list[str]:
        """Return all keys at a specific level, or all unique keys across levels."""
        if level is not None:
            return sorted(self._store.get(level, {}).keys())
        seen: set[str] = set()
        for lvl in LEVELS:
            seen.update(self._store[lvl].keys())
        return sorted(seen)

    def list_entries(self, level: str | None = None) -> list[MemoryEntry]:
        """Return all entries at a level, or all entries across levels."""
        if level is not None:
            return sorted(self._store.get(level, {}).values(), key=lambda e: e.key)
        entries: list[MemoryEntry] = []
        for lvl in LEVELS:
            entries.extend(self._store[lvl].values())
        return sorted(entries, key=lambda e: (e.level, e.key))

    def effective_snapshot(self) -> dict[str, Any]:
        """Return the effective (resolved) key→value map after cascade."""
        result: dict[str, Any] = {}
        # Iterate from least specific to most specific, letting later values win
        for level in reversed(LEVELS):
            for key, entry in self._store[level].items():
                result[key] = entry.value
        return result

    def search(self, query: str, level: str | None = None) -> list[MemoryEntry]:
        """Return entries whose key, value str, or description contain *query*."""
        query_lower = query.lower()
        entries = self.list_entries(level=level)
        return [
            e for e in entries
            if query_lower in e.key.lower()
            or query_lower in str(e.value).lower()
            or query_lower in e.description.lower()
        ]
