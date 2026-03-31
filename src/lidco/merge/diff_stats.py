"""Diff statistics — compute additions, deletions, similarity (stdlib only)."""
from __future__ import annotations

import difflib
from dataclasses import dataclass


@dataclass
class FileDiffStats:
    """Statistics for a single file diff."""

    file_path: str
    additions: int
    deletions: int
    changes: int
    similarity: float


class DiffStatsCollector:
    """Collect and format diff statistics."""

    def compute(self, old: str, new: str, file_path: str = "") -> FileDiffStats:
        """Compute diff stats between *old* and *new* content."""
        old_lines = old.splitlines()
        new_lines = new.splitlines()

        sm = difflib.SequenceMatcher(None, old_lines, new_lines)
        similarity = sm.ratio()

        additions = 0
        deletions = 0
        changes = 0

        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "insert":
                additions += j2 - j1
            elif tag == "delete":
                deletions += i2 - i1
            elif tag == "replace":
                deletions += i2 - i1
                additions += j2 - j1
                changes += 1

        return FileDiffStats(
            file_path=file_path,
            additions=additions,
            deletions=deletions,
            changes=changes,
            similarity=similarity,
        )

    def compute_batch(
        self, diffs: list[tuple[str, str, str]]
    ) -> list[FileDiffStats]:
        """Compute stats for multiple files. Each tuple is (path, old, new)."""
        return [self.compute(old, new, path) for path, old, new in diffs]

    def summary(self, stats: list[FileDiffStats]) -> dict:
        """Aggregate statistics across files."""
        total_add = sum(s.additions for s in stats)
        total_del = sum(s.deletions for s in stats)
        files_changed = len([s for s in stats if s.additions or s.deletions])
        return {
            "total_additions": total_add,
            "total_deletions": total_del,
            "files_changed": files_changed,
        }

    def format_stat_line(self, stat: FileDiffStats) -> str:
        """Format a single stat line, e.g. ``file.py | 10 ++ 3 --``."""
        path = stat.file_path or "(unknown)"
        plus = f"{stat.additions} ++" if stat.additions else ""
        minus = f"{stat.deletions} --" if stat.deletions else ""
        parts = [p for p in (plus, minus) if p]
        return f"{path} | {' '.join(parts)}" if parts else f"{path} | (no changes)"

    def format_summary(self, stats: list[FileDiffStats]) -> str:
        """Format a git-like diff summary."""
        lines: list[str] = []
        for s in stats:
            lines.append(self.format_stat_line(s))
        s = self.summary(stats)
        lines.append("")
        lines.append(
            f"{s['files_changed']} file(s) changed, "
            f"{s['total_additions']} insertion(s)(+), "
            f"{s['total_deletions']} deletion(s)(-)"
        )
        return "\n".join(lines)
