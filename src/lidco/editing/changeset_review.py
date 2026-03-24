"""Changeset Reviewer — T585.

Collects file edits into a unified changeset, formats diffs,
and supports selective / partial hunk application.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class FileChange:
    path: str
    original: str
    proposed: str
    diff_text: str
    hunk_count: int
    lines_added: int
    lines_removed: int


@dataclass
class Changeset:
    changes: list[FileChange]
    total_files: int
    total_hunks: int
    summary: str


@dataclass
class ChangesetDecision:
    accepted_files: set
    rejected_files: set
    partial: dict  # {file_path: set of accepted hunk indices}


@dataclass
class ApplyResult:
    applied_files: int
    skipped_files: int
    errors: list[str]


class ChangesetReviewer:
    """Review, format, and selectively apply file changesets."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect(self, edits: dict[str, tuple[str, str]]) -> Changeset:
        """Build a Changeset from ``{path: (old_content, new_content)}``."""
        changes: list[FileChange] = []
        for path, (old, new) in edits.items():
            old_lines = old.splitlines(keepends=True)
            new_lines = new.splitlines(keepends=True)
            diff_lines = list(
                difflib.unified_diff(
                    old_lines,
                    new_lines,
                    fromfile=f"{path} (original)",
                    tofile=f"{path} (proposed)",
                    lineterm="",
                )
            )
            hunk_count = self._count_hunks(diff_lines)
            added, removed = self._count_additions_deletions(diff_lines)
            diff_text = "\n".join(diff_lines)
            changes.append(
                FileChange(
                    path=path,
                    original=old,
                    proposed=new,
                    diff_text=diff_text,
                    hunk_count=hunk_count,
                    lines_added=added,
                    lines_removed=removed,
                )
            )
        total_hunks = sum(c.hunk_count for c in changes)
        total_added = sum(c.lines_added for c in changes)
        total_removed = sum(c.lines_removed for c in changes)
        summary = self._build_summary(changes, total_added, total_removed)
        return Changeset(
            changes=changes,
            total_files=len(changes),
            total_hunks=total_hunks,
            summary=summary,
        )

    def format_summary(self, changeset: Changeset) -> str:
        """One-line-per-file summary plus a total line."""
        lines: list[str] = []
        for ch in changeset.changes:
            lines.append(
                f"M {ch.path} (+{ch.lines_added} -{ch.lines_removed}, "
                f"{ch.hunk_count} hunks)"
            )
        total_added = sum(c.lines_added for c in changeset.changes)
        total_removed = sum(c.lines_removed for c in changeset.changes)
        lines.append(
            f"{changeset.total_files} files changed, "
            f"+{total_added} -{total_removed}"
        )
        return "\n".join(lines)

    def format_full(self, changeset: Changeset) -> str:
        """Full unified diff of all files with separators."""
        if not changeset.changes:
            return ""
        blocks: list[str] = []
        for ch in changeset.changes:
            blocks.append(f"=== {ch.path} ===")
            blocks.append(ch.diff_text)
        return "\n".join(blocks)

    def apply(
        self, changeset: Changeset, decision: ChangesetDecision
    ) -> ApplyResult:
        """Apply accepted files, skip rejected, handle partial hunks."""
        applied = 0
        skipped = 0
        errors: list[str] = []

        for ch in changeset.changes:
            if ch.path in decision.partial:
                # Partial hunk application
                try:
                    content = self._apply_partial(ch, decision.partial[ch.path])
                    Path(ch.path).write_text(content)
                    applied += 1
                except Exception as exc:
                    errors.append(f"{ch.path}: {exc}")
            elif ch.path in decision.accepted_files:
                try:
                    Path(ch.path).write_text(ch.proposed)
                    applied += 1
                except Exception as exc:
                    errors.append(f"{ch.path}: {exc}")
            else:
                skipped += 1

        return ApplyResult(
            applied_files=applied, skipped_files=skipped, errors=errors
        )

    def apply_all(self, changeset: Changeset) -> ApplyResult:
        """Accept every change in the changeset."""
        decision = ChangesetDecision(
            accepted_files={ch.path for ch in changeset.changes},
            rejected_files=set(),
            partial={},
        )
        return self.apply(changeset, decision)

    def reject_all(self, changeset: Changeset) -> ApplyResult:
        """Reject every change — nothing is written."""
        return ApplyResult(
            applied_files=0,
            skipped_files=changeset.total_files,
            errors=[],
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _count_hunks(self, diff_lines: list[str]) -> int:
        """Count ``@@`` markers in diff output."""
        return sum(1 for line in diff_lines if line.startswith("@@"))

    def _count_additions_deletions(
        self, diff_lines: list[str]
    ) -> tuple[int, int]:
        """Count ``+``/``-`` lines excluding ``+++``/``---`` headers."""
        added = 0
        removed = 0
        for line in diff_lines:
            if line.startswith("+++") or line.startswith("---"):
                continue
            if line.startswith("+"):
                added += 1
            elif line.startswith("-"):
                removed += 1
        return added, removed

    def _apply_partial(
        self, change: FileChange, hunk_indices: set[int]
    ) -> str:
        """Apply only the specified hunk indices to the original content.

        Parses the unified diff into hunk blocks, then replays only the
        selected hunks against the original text line-by-line.
        """
        diff_lines = change.diff_text.split("\n")

        # Parse hunks: list of (start_old (0-based), list[diff_line])
        hunks: list[tuple[int, list[str]]] = []
        current_hunk_lines: list[str] = []
        current_start: int = 0

        for line in diff_lines:
            if line.startswith("@@"):
                if current_hunk_lines:
                    hunks.append((current_start, current_hunk_lines))
                    current_hunk_lines = []
                # Parse @@ -start,count +start,count @@
                parts = line.split("@@")
                if len(parts) >= 2:
                    range_info = parts[1].strip()
                    old_range = range_info.split()[0]  # -start,count
                    start_str = old_range.lstrip("-").split(",")[0]
                    current_start = int(start_str) - 1  # to 0-based
            elif line.startswith("---") or line.startswith("+++"):
                continue
            else:
                current_hunk_lines.append(line)

        if current_hunk_lines:
            hunks.append((current_start, current_hunk_lines))

        # Build result by replaying selected hunks on original lines
        original_lines = change.original.splitlines(keepends=True)
        result_lines: list[str] = []
        orig_idx = 0

        # Sort hunks by their start position
        indexed_hunks = sorted(enumerate(hunks), key=lambda x: x[1][0])

        for hunk_idx, (start, hunk_lines) in indexed_hunks:
            if hunk_idx not in hunk_indices:
                # Skip this hunk — consume original lines through the hunk
                # We need to figure out how many original lines this hunk spans
                hunk_orig_count = sum(
                    1
                    for hl in hunk_lines
                    if hl.startswith(" ") or hl.startswith("-")
                )
                # Copy original lines up to and through this hunk
                end = start + hunk_orig_count
                while orig_idx < end and orig_idx < len(original_lines):
                    result_lines.append(original_lines[orig_idx])
                    orig_idx += 1
            else:
                # Copy original lines before this hunk
                while orig_idx < start:
                    result_lines.append(original_lines[orig_idx])
                    orig_idx += 1
                # Apply the hunk
                for hl in hunk_lines:
                    if hl.startswith(" "):
                        # Context line — advance original
                        result_lines.append(original_lines[orig_idx])
                        orig_idx += 1
                    elif hl.startswith("-"):
                        # Deletion — skip original line
                        orig_idx += 1
                    elif hl.startswith("+"):
                        # Addition — add new line
                        # Restore the trailing newline that splitlines
                        # would have kept
                        text = hl[1:]
                        if not text.endswith("\n"):
                            text += "\n"
                        result_lines.append(text)

        # Copy remaining original lines
        while orig_idx < len(original_lines):
            result_lines.append(original_lines[orig_idx])
            orig_idx += 1

        return "".join(result_lines)

    def _build_summary(
        self,
        changes: list[FileChange],
        total_added: int,
        total_removed: int,
    ) -> str:
        lines = [
            f"M {c.path} (+{c.lines_added} -{c.lines_removed})"
            for c in changes
        ]
        lines.append(
            f"{len(changes)} files changed, +{total_added} -{total_removed}"
        )
        return "\n".join(lines)
