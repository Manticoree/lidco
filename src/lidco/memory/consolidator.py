"""Periodically compact similar/stale memory entries to prevent memory bloat."""

import math
import re
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class ConsolidationReport:
    original_count: int
    consolidated_count: int
    merged_groups: int
    removed_stale: int
    summary: str


class MemoryConsolidator:
    """Merges similar memory entries and removes stale ones."""

    def __init__(
        self,
        similarity_threshold: float = 0.75,
        staleness_ttl_days: float = 90.0,
        max_group_size: int = 5,
    ):
        self.similarity_threshold = similarity_threshold
        self.staleness_ttl_days = staleness_ttl_days
        self.max_group_size = max_group_size

    def _tokenize(self, text: str) -> dict[str, int]:
        """Simple term-frequency tokenizer."""
        tokens = re.findall(r"\w+", text.lower())
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        return tf

    def _cosine(self, a: dict[str, int], b: dict[str, int]) -> float:
        """Cosine similarity between two TF dicts."""
        dot = sum(a.get(k, 0) * b.get(k, 0) for k in a)
        mag_a = math.sqrt(sum(v * v for v in a.values()))
        mag_b = math.sqrt(sum(v * v for v in b.values()))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    def _similarity(self, a: str, b: str) -> float:
        return self._cosine(self._tokenize(a), self._tokenize(b))

    def find_similar_groups(self, memories: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        """Cluster memories by content similarity >= threshold.

        Each entry: {"id": str, "content": str, "created_at": float,
                     "use_count": int, "tags": list}
        Entries with use_count > 10 are exempt from grouping.
        Groups capped at max_group_size.
        """
        exempt = {i for i, m in enumerate(memories) if m.get("use_count", 0) > 10}
        used: set[int] = set()
        groups: list[list[dict[str, Any]]] = []
        for i, mi in enumerate(memories):
            if i in used or i in exempt:
                continue
            group = [mi]
            used.add(i)
            for j, mj in enumerate(memories):
                if j in used or j in exempt:
                    continue
                if len(group) >= self.max_group_size:
                    break
                sim = self._similarity(mi.get("content", ""), mj.get("content", ""))
                if sim >= self.similarity_threshold:
                    group.append(mj)
                    used.add(j)
            if len(group) > 1:
                groups.append(group)
        return groups

    def merge_group(self, group: list[dict[str, Any]]) -> dict[str, Any]:
        """Merge a group into one entry.

        - Combine unique content lines
        - Union tags
        - Keep earliest created_at
        - Sum use_counts
        - Keep highest priority
        """
        all_lines: list[str] = []
        seen: set[str] = set()
        for entry in group:
            for line in entry.get("content", "").splitlines():
                stripped = line.strip()
                if stripped and stripped not in seen:
                    seen.add(stripped)
                    all_lines.append(stripped)

        all_tags = list({t for e in group for t in e.get("tags", [])})
        earliest = min(e.get("created_at", time.time()) for e in group)
        total_use = sum(e.get("use_count", 0) for e in group)
        max_priority = max(e.get("priority", 1) for e in group)
        base_id = group[0].get("id", "merged") + "_consolidated"

        return {
            "id": base_id,
            "content": "\n".join(all_lines),
            "tags": all_tags,
            "created_at": earliest,
            "use_count": total_use,
            "priority": max_priority,
        }

    def consolidate(self, store: Any) -> ConsolidationReport:
        """Full pipeline:

        1. Remove stale entries (older than staleness_ttl_days and use_count == 0)
        2. Find similar groups
        3. Merge groups: delete originals, insert merged
        Returns report.
        """
        memories = list(store.list_all())
        original_count = len(memories)

        # Step 1: Remove stale
        cutoff = time.time() - self.staleness_ttl_days * 86400
        stale = [
            m
            for m in memories
            if m.get("created_at", time.time()) < cutoff and m.get("use_count", 0) == 0
        ]
        for m in stale:
            store.delete(m["id"])
        removed_stale = len(stale)

        # Reload after stale removal
        memories = [m for m in memories if m not in stale]

        # Step 2: Find similar groups
        groups = self.find_similar_groups(memories)

        # Step 3: Merge
        for group in groups:
            merged = self.merge_group(group)
            for m in group:
                store.delete(m["id"])
            store.save(merged)

        final_count = len(list(store.list_all()))
        merged_groups = len(groups)

        return ConsolidationReport(
            original_count=original_count,
            consolidated_count=final_count,
            merged_groups=merged_groups,
            removed_stale=removed_stale,
            summary=(
                f"Merged {merged_groups} groups, removed {removed_stale} stale. "
                f"{original_count}\u2192{final_count} entries."
            ),
        )

    def dry_run(self, store: Any) -> ConsolidationReport:
        """Same as consolidate() but does not modify store."""
        memories = list(store.list_all())
        original_count = len(memories)

        cutoff = time.time() - self.staleness_ttl_days * 86400
        stale = [
            m
            for m in memories
            if m.get("created_at", time.time()) < cutoff and m.get("use_count", 0) == 0
        ]
        removed_stale = len(stale)

        non_stale = [m for m in memories if m not in stale]
        groups = self.find_similar_groups(non_stale)
        merged_count = original_count - sum(len(g) - 1 for g in groups) - removed_stale

        return ConsolidationReport(
            original_count=original_count,
            consolidated_count=merged_count,
            merged_groups=len(groups),
            removed_stale=removed_stale,
            summary=f"[dry-run] Would merge {len(groups)} groups, remove {removed_stale} stale.",
        )
