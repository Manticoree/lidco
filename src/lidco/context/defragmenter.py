"""Context Defragmenter — compacts and merges context segments (stdlib only).

Works with ContextSegments to reclaim wasted token budget by compacting
entries within segments and merging small under-used segments.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lidco.context.segments import ContextSegments, Segment


@dataclass(frozen=True)
class DefragResult:
    """Result of a defragmentation pass."""

    merged_count: int
    reclaimed_tokens: int


class ContextDefragmenter:
    """Compacts and merges context segments to reclaim token budget."""

    def __init__(self, segments: ContextSegments) -> None:
        self._segments = segments
        self._defrag_count: int = 0
        self._total_reclaimed: int = 0

    # ------------------------------------------------------------------ #
    # Compaction                                                          #
    # ------------------------------------------------------------------ #

    def compact(self, segment_name: str) -> int:
        """Compact a segment by recalculating used tokens.  Returns tokens reclaimed."""
        seg = self._segments.get_segment(segment_name)
        if seg is None:
            return 0
        actual_used = sum(max(1, len(e) // 4) for e in seg.entries)
        reclaimed = max(0, seg.used - actual_used)
        if reclaimed > 0:
            # Replace with accurate count
            updated = Segment(
                name=seg.name,
                budget=seg.budget,
                used=actual_used,
                entries=list(seg.entries),
            )
            self._segments._segments = {
                **self._segments._segments,
                segment_name: updated,
            }
            self._total_reclaimed += reclaimed
        return reclaimed

    # ------------------------------------------------------------------ #
    # Merge                                                               #
    # ------------------------------------------------------------------ #

    def merge_small(self, threshold: int = 100) -> int:
        """Merge segments with total used tokens below *threshold* into a '_merged' segment.

        Returns the number of segments merged.
        """
        to_merge: list[Segment] = []
        to_keep: dict[str, Segment] = {}
        for seg in self._segments.list_segments():
            if seg.used < threshold and seg.name != "_merged":
                to_merge.append(seg)
            else:
                to_keep[seg.name] = seg

        if len(to_merge) < 2:
            return 0

        # Build merged segment
        merged_entries: list[str] = []
        merged_used = 0
        merged_budget = 0
        for seg in to_merge:
            merged_entries.extend(seg.entries)
            merged_used += seg.used
            merged_budget += seg.budget

        existing_merged = to_keep.get("_merged")
        if existing_merged is not None:
            merged_entries = [*existing_merged.entries, *merged_entries]
            merged_used += existing_merged.used
            merged_budget += existing_merged.budget

        to_keep["_merged"] = Segment(
            name="_merged",
            budget=merged_budget,
            used=merged_used,
            entries=merged_entries,
        )
        self._segments._segments = dict(to_keep)
        return len(to_merge)

    # ------------------------------------------------------------------ #
    # Full defrag                                                         #
    # ------------------------------------------------------------------ #

    def defragment(self) -> DefragResult:
        """Run a full defragmentation: compact all segments, then merge small ones."""
        reclaimed = 0
        for seg in self._segments.list_segments():
            reclaimed += self.compact(seg.name)
        merged = self.merge_small()
        self._defrag_count += 1
        self._total_reclaimed += reclaimed
        return DefragResult(merged_count=merged, reclaimed_tokens=reclaimed)

    # ------------------------------------------------------------------ #
    # Introspection                                                       #
    # ------------------------------------------------------------------ #

    def stats(self) -> dict[str, Any]:
        return {
            "defrag_count": self._defrag_count,
            "total_reclaimed": self._total_reclaimed,
            "segment_count": len(self._segments.list_segments()),
        }
