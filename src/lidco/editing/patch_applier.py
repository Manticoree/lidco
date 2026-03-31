"""Patch Applier — apply unified diff PatchFile hunks to text content.

Stdlib only — no external deps.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from lidco.editing.patch_parser import PatchFile, PatchHunk


class ApplyError(Exception):
    """Raised when a patch cannot be applied."""


@dataclass
class PatchApplyResult:
    """Result of applying a patch."""
    success: bool
    result_text: str
    error: str = ""


class PatchApplier:
    """Apply PatchFile hunks to original text."""

    def apply(self, original: str, patch_file: PatchFile, strict: bool = False) -> PatchApplyResult:
        """Apply all hunks from patch_file to original text.

        If strict=False, fuzzy matching is attempted on mismatch (±3 lines).
        """
        lines = original.splitlines(keepends=True)
        # Ensure lines end with newline for consistent processing
        offset = 0  # accumulated offset from previous hunks
        result_lines = list(lines)

        for hunk in patch_file.hunks:
            try:
                result_lines, offset = _apply_hunk(result_lines, hunk, offset, strict)
            except ApplyError as e:
                return PatchApplyResult(success=False, result_text=original, error=str(e))

        return PatchApplyResult(success=True, result_text="".join(result_lines))

    def dry_run(self, original: str, patch_file: PatchFile) -> PatchApplyResult:
        """Simulate applying the patch without modifying original."""
        return self.apply(original, patch_file, strict=False)


def _apply_hunk(
    lines: list[str],
    hunk: PatchHunk,
    offset: int,
    strict: bool,
) -> tuple[list[str], int]:
    """Apply one hunk to lines (mutates a copy). Returns (new_lines, new_offset)."""
    # Expected start position (1-based → 0-based)
    start = hunk.old_start - 1 + offset

    # Extract context lines from hunk for fuzzy match
    context_lines = [l[1:] for l in hunk.lines if l.startswith(" ") or l.startswith("-")]

    actual_start = start
    if not strict:
        actual_start = _fuzzy_find(lines, start, context_lines)

    # Build new lines from hunk
    new_chunk: list[str] = []
    removed = 0
    for line in hunk.lines:
        tag = line[0] if line else " "
        content = line[1:] if line else ""
        if tag == " ":
            # context line — keep
            new_chunk.append(content)
        elif tag == "+":
            new_chunk.append(content)
        elif tag == "-":
            removed += 1
        else:
            new_chunk.append(line)

    # Count how many old lines to remove
    old_count = sum(1 for l in hunk.lines if l.startswith("-") or l.startswith(" "))

    # Ensure trailing newlines on chunk lines
    new_chunk = _ensure_newlines(new_chunk)

    # Splice
    result = lines[:actual_start] + new_chunk + lines[actual_start + old_count:]
    new_offset = offset + (len(new_chunk) - old_count)
    return result, new_offset


def _fuzzy_find(lines: list[str], expected_start: int, context: list[str]) -> int:
    """Try to find the best match for context within ±3 of expected_start."""
    if not context:
        return expected_start
    search_range = range(max(0, expected_start - 3), min(len(lines), expected_start + 4))
    best = expected_start
    best_score = -1
    for i in search_range:
        score = _match_score(lines, i, context)
        if score > best_score:
            best_score = score
            best = i
    return best


def _match_score(lines: list[str], start: int, context: list[str]) -> int:
    """Count matching context lines starting at position start."""
    score = 0
    for j, c in enumerate(context):
        idx = start + j
        if idx < len(lines):
            if lines[idx].rstrip("\n\r") == c.rstrip("\n\r"):
                score += 1
    return score


def _ensure_newlines(chunk: list[str]) -> list[str]:
    """Ensure each line ends with a newline if it doesn't."""
    result = []
    for line in chunk:
        if line and not line.endswith("\n"):
            result.append(line + "\n")
        else:
            result.append(line)
    return result
