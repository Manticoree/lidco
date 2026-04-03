"""Context Segments — partitioned budget management for context window (stdlib only).

Divides the context window into named segments, each with its own token
budget.  Entries are added to specific segments and tracked against the
segment budget.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Segment:
    """A named context segment with a token budget."""

    name: str
    budget: int
    used: int = 0
    entries: list[str] = field(default_factory=list)


class ContextSegments:
    """Manages a collection of named context segments."""

    def __init__(self) -> None:
        self._segments: dict[str, Segment] = {}

    # ------------------------------------------------------------------ #
    # Factory                                                             #
    # ------------------------------------------------------------------ #

    @classmethod
    def with_defaults(cls) -> ContextSegments:
        """Create an instance with system/tools/history/active segments."""
        inst = cls()
        inst.create_segment("system", budget=2000)
        inst.create_segment("tools", budget=4000)
        inst.create_segment("history", budget=8000)
        inst.create_segment("active", budget=16000)
        return inst

    # ------------------------------------------------------------------ #
    # Segment lifecycle                                                   #
    # ------------------------------------------------------------------ #

    def create_segment(self, name: str, budget: int) -> None:
        """Create a new segment.  Raises ValueError if it already exists."""
        if name in self._segments:
            raise ValueError(f"Segment '{name}' already exists")
        self._segments = {**self._segments, name: Segment(name=name, budget=budget)}

    def get_segment(self, name: str) -> Segment | None:
        return self._segments.get(name)

    def list_segments(self) -> list[Segment]:
        return list(self._segments.values())

    # ------------------------------------------------------------------ #
    # Entry management                                                    #
    # ------------------------------------------------------------------ #

    def add_to_segment(self, name: str, entry: str) -> bool:
        """Add an entry (token string) to a segment.  Returns False if over budget or missing."""
        seg = self._segments.get(name)
        if seg is None:
            return False
        token_cost = max(1, len(entry) // 4)
        if seg.used + token_cost > seg.budget:
            return False
        updated = Segment(
            name=seg.name,
            budget=seg.budget,
            used=seg.used + token_cost,
            entries=[*seg.entries, entry],
        )
        self._segments = {**self._segments, name: updated}
        return True

    def remove_from_segment(self, name: str, entry: str) -> bool:
        """Remove an entry from a segment.  Returns False if not found."""
        seg = self._segments.get(name)
        if seg is None or entry not in seg.entries:
            return False
        token_cost = max(1, len(entry) // 4)
        new_entries = [e for e in seg.entries if e != entry]
        # If duplicates existed, only remove the cost of one
        updated = Segment(
            name=seg.name,
            budget=seg.budget,
            used=max(0, seg.used - token_cost),
            entries=new_entries,
        )
        self._segments = {**self._segments, name: updated}
        return True

    def resize(self, name: str, new_budget: int) -> bool:
        """Resize a segment's budget.  Returns False if segment not found."""
        seg = self._segments.get(name)
        if seg is None:
            return False
        updated = Segment(
            name=seg.name,
            budget=new_budget,
            used=seg.used,
            entries=list(seg.entries),
        )
        self._segments = {**self._segments, name: updated}
        return True

    # ------------------------------------------------------------------ #
    # Introspection                                                       #
    # ------------------------------------------------------------------ #

    def stats(self) -> dict[str, Any]:
        total_budget = sum(s.budget for s in self._segments.values())
        total_used = sum(s.used for s in self._segments.values())
        return {
            "segment_count": len(self._segments),
            "total_budget": total_budget,
            "total_used": total_used,
            "segments": {s.name: {"budget": s.budget, "used": s.used, "entries": len(s.entries)} for s in self._segments.values()},
        }
