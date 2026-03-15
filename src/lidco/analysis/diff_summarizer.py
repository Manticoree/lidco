"""Unified diff summarization — Task 336."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DiffHunk:
    file_path: str
    additions: int
    deletions: int


@dataclass
class DiffSummary:
    files_changed: int
    total_additions: int
    total_deletions: int
    hunks: list[DiffHunk] = field(default_factory=list)

    def by_file(self) -> dict[str, DiffHunk]:
        """Merge all hunks into a per-file summary."""
        result: dict[str, tuple[int, int]] = {}
        for h in self.hunks:
            adds, dels = result.get(h.file_path, (0, 0))
            result[h.file_path] = (adds + h.additions, dels + h.deletions)
        return {
            fp: DiffHunk(file_path=fp, additions=a, deletions=d)
            for fp, (a, d) in result.items()
        }


_DIFF_HEADER_RE = re.compile(r"^diff --git a/.+ b/(.+)$")
_PLUS_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$")
_MINUS_FILE_RE = re.compile(r"^--- a/(.+)$")


class DiffSummarizer:
    """Parses unified diff text into a DiffSummary."""

    def parse(self, diff_text: str) -> DiffSummary:
        """Parse a unified diff string and return a DiffSummary."""
        if not diff_text or not diff_text.strip():
            return DiffSummary(files_changed=0, total_additions=0, total_deletions=0)

        hunks: list[DiffHunk] = []
        current_file: str = ""
        additions = 0
        deletions = 0

        for line in diff_text.splitlines():
            # New file section
            m = _DIFF_HEADER_RE.match(line)
            if m:
                if current_file:
                    hunks.append(
                        DiffHunk(
                            file_path=current_file,
                            additions=additions,
                            deletions=deletions,
                        )
                    )
                current_file = m.group(1)
                additions = 0
                deletions = 0
                continue

            # Override file path from +++ line (handles renames, new files, etc.)
            m2 = _PLUS_FILE_RE.match(line)
            if m2:
                current_file = m2.group(1)
                continue

            # Count additions (skip +++ header lines)
            if line.startswith("+") and not line.startswith("+++"):
                additions += 1
                continue

            # Count deletions (skip --- header lines)
            if line.startswith("-") and not line.startswith("---"):
                deletions += 1
                continue

        # Flush last file
        if current_file:
            hunks.append(
                DiffHunk(
                    file_path=current_file,
                    additions=additions,
                    deletions=deletions,
                )
            )

        total_adds = sum(h.additions for h in hunks)
        total_dels = sum(h.deletions for h in hunks)

        return DiffSummary(
            files_changed=len(hunks),
            total_additions=total_adds,
            total_deletions=total_dels,
            hunks=hunks,
        )
