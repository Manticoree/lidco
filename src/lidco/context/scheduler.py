"""Context Scheduler — priority-based scheduling for context entries (stdlib only).

Selects the highest-priority context entries that fit within a token budget.
Supports preemption of low-priority entries to make room for higher ones.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContextEntry:
    """A single schedulable context entry."""

    id: str
    content: str
    priority: int
    category: str
    token_estimate: int


class ContextScheduler:
    """Priority-based scheduler for context window entries."""

    def __init__(self) -> None:
        self._entries: dict[str, ContextEntry] = {}
        self._schedule_count: int = 0
        self._preempt_count: int = 0

    # ------------------------------------------------------------------ #
    # Mutation (returns new state conceptually; internal dict is replaced) #
    # ------------------------------------------------------------------ #

    def add(self, entry: ContextEntry) -> None:
        """Add an entry to the scheduler."""
        self._entries = {**self._entries, entry.id: entry}

    def remove(self, entry_id: str) -> bool:
        """Remove an entry by id.  Returns True if it existed."""
        if entry_id not in self._entries:
            return False
        self._entries = {k: v for k, v in self._entries.items() if k != entry_id}
        return True

    # ------------------------------------------------------------------ #
    # Scheduling                                                          #
    # ------------------------------------------------------------------ #

    def schedule(self, budget: int) -> list[ContextEntry]:
        """Select entries by descending priority that fit within *budget* tokens."""
        sorted_entries = sorted(
            self._entries.values(), key=lambda e: e.priority, reverse=True
        )
        selected: list[ContextEntry] = []
        used = 0
        for entry in sorted_entries:
            if used + entry.token_estimate <= budget:
                selected.append(entry)
                used += entry.token_estimate
        self._schedule_count += 1
        return selected

    def preempt(self, entry_id: str) -> bool:
        """Remove the lowest-priority entry to make room for *entry_id*.

        Returns True if a lower-priority entry was evicted, False otherwise.
        """
        target = self._entries.get(entry_id)
        if target is None:
            return False

        # Find the lowest-priority entry that is NOT the target
        candidates = [e for e in self._entries.values() if e.id != entry_id]
        if not candidates:
            return False

        victim = min(candidates, key=lambda e: e.priority)
        if victim.priority >= target.priority:
            return False

        self._entries = {k: v for k, v in self._entries.items() if k != victim.id}
        self._preempt_count += 1
        return True

    # ------------------------------------------------------------------ #
    # Introspection                                                       #
    # ------------------------------------------------------------------ #

    def get(self, entry_id: str) -> ContextEntry | None:
        return self._entries.get(entry_id)

    @property
    def entries(self) -> list[ContextEntry]:
        return list(self._entries.values())

    def stats(self) -> dict[str, Any]:
        total_tokens = sum(e.token_estimate for e in self._entries.values())
        categories: dict[str, int] = {}
        for e in self._entries.values():
            categories[e.category] = categories.get(e.category, 0) + 1
        return {
            "entry_count": len(self._entries),
            "total_tokens": total_tokens,
            "schedule_count": self._schedule_count,
            "preempt_count": self._preempt_count,
            "categories": categories,
        }
