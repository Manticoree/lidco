"""Lazy Tool Schema Registry — defer schema resolution until needed."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class LazyToolEntry:
    """A tool entry whose full schema may be deferred."""

    name: str
    description: str
    schema_fn: Callable[[], dict] | None = None
    _cached_schema: dict | None = field(default=None, repr=False)

    @property
    def resolved(self) -> bool:
        return self._cached_schema is not None


class LazyToolRegistry:
    """Registry that stores tool stubs and resolves full schemas on demand."""

    def __init__(self) -> None:
        self._entries: dict[str, LazyToolEntry] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_stub(
        self,
        name: str,
        description: str,
        schema_fn: Callable[[], dict],
    ) -> None:
        """Register a tool by name/description only; schema loaded lazily via *schema_fn*."""
        self._entries[name] = LazyToolEntry(
            name=name,
            description=description,
            schema_fn=schema_fn,
            _cached_schema=None,
        )

    def register_full(self, name: str, description: str, schema: dict) -> None:
        """Register a tool with its full schema immediately (eager)."""
        self._entries[name] = LazyToolEntry(
            name=name,
            description=description,
            schema_fn=None,
            _cached_schema=dict(schema),
        )

    # ------------------------------------------------------------------
    # Query / Resolution
    # ------------------------------------------------------------------

    def search(self, query: str, max_results: int = 5) -> list[LazyToolEntry]:
        """Keyword search across tool names and descriptions (case-insensitive)."""
        query_lower = query.lower()
        tokens = query_lower.split()
        scored: list[tuple[int, LazyToolEntry]] = []
        for entry in self._entries.values():
            haystack = f"{entry.name} {entry.description}".lower()
            score = sum(1 for tok in tokens if tok in haystack)
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda t: (-t[0], t[1].name))
        return [entry for _, entry in scored[:max_results]]

    def resolve(self, name: str) -> dict | None:
        """Resolve full schema for *name*. Returns cached schema or calls schema_fn."""
        entry = self._entries.get(name)
        if entry is None:
            return None
        if entry._cached_schema is not None:
            return dict(entry._cached_schema)
        if entry.schema_fn is not None:
            schema = entry.schema_fn()
            entry._cached_schema = dict(schema)
            return dict(schema)
        return None

    def list_names(self) -> list[str]:
        """Return sorted list of all registered tool names."""
        return sorted(self._entries.keys())

    def list_stubs(self) -> list[LazyToolEntry]:
        """Return all entries without resolving any schemas."""
        return list(self._entries.values())

    def stats(self) -> dict:
        """Return counts: total, resolved, pending."""
        total = len(self._entries)
        resolved = sum(1 for e in self._entries.values() if e.resolved)
        return {
            "total": total,
            "resolved": resolved,
            "pending": total - resolved,
        }
