"""AI-powered git conflict resolver (Task 375)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator


@dataclass
class ConflictBlock:
    """Represents a single git merge conflict block."""

    file: str
    ours: str
    theirs: str
    context_before: str = ""
    context_after: str = ""
    start_line: int = 0


_OURS_RE = re.compile(r"^<{7} (.+)$")
_SEP_RE = re.compile(r"^={7}$")
_THEIRS_RE = re.compile(r"^>{7} (.+)$")
_CONTEXT_LINES = 5


def parse_conflict_blocks(file_path: str) -> list[ConflictBlock]:
    """Parse all conflict blocks from a file.

    Returns a list of ConflictBlock instances found in the file.
    Returns an empty list if the file cannot be read or has no conflicts.
    """
    try:
        content = Path(file_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    lines = content.splitlines()
    blocks: list[ConflictBlock] = []

    i = 0
    while i < len(lines):
        if _OURS_RE.match(lines[i]):
            block_start = i
            ours_lines: list[str] = []
            theirs_lines: list[str] = []
            in_ours = True
            i += 1
            while i < len(lines):
                if _SEP_RE.match(lines[i]):
                    in_ours = False
                    i += 1
                    continue
                if _THEIRS_RE.match(lines[i]):
                    break
                if in_ours:
                    ours_lines.append(lines[i])
                else:
                    theirs_lines.append(lines[i])
                i += 1

            # context before
            ctx_before_start = max(0, block_start - _CONTEXT_LINES)
            ctx_before = "\n".join(lines[ctx_before_start:block_start])

            # context after
            ctx_after_end = min(len(lines), i + 1 + _CONTEXT_LINES)
            ctx_after = "\n".join(lines[i + 1 : ctx_after_end])

            blocks.append(
                ConflictBlock(
                    file=file_path,
                    ours="\n".join(ours_lines),
                    theirs="\n".join(theirs_lines),
                    context_before=ctx_before,
                    context_after=ctx_after,
                    start_line=block_start + 1,
                )
            )
        i += 1

    return blocks


def find_conflicted_files(project_dir: str | None = None) -> list[str]:
    """Return list of files with conflict markers via git status."""
    import subprocess

    cwd = project_dir or "."
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            cwd=cwd,
        )
        if result.returncode == 0:
            return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: scan for conflict markers
    try:
        result2 = subprocess.run(
            ["git", "ls-files", "-u", "--deduplicate"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            cwd=cwd,
        )
        if result2.returncode == 0:
            seen: set[str] = set()
            files: list[str] = []
            for line in result2.stdout.splitlines():
                parts = line.split("\t", 1)
                if len(parts) == 2:
                    fname = parts[1].strip()
                    if fname not in seen:
                        seen.add(fname)
                        files.append(fname)
            return files
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return []


def apply_resolution(file_path: str, blocks: list[ConflictBlock], resolutions: list[str]) -> bool:
    """Apply resolved content back to a file, replacing conflict markers.

    resolutions[i] is the chosen text for blocks[i].
    Returns True on success.
    """
    try:
        content = Path(file_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False

    lines = content.splitlines(keepends=True)
    result_lines: list[str] = []
    i = 0
    block_idx = 0

    while i < len(lines):
        line = lines[i].rstrip("\n").rstrip("\r")
        if block_idx < len(blocks) and _OURS_RE.match(line):
            # skip until end of conflict block
            while i < len(lines):
                cur = lines[i].rstrip("\n").rstrip("\r")
                if _THEIRS_RE.match(cur):
                    i += 1
                    break
                i += 1
            # insert resolution
            resolution = resolutions[block_idx] if block_idx < len(resolutions) else ""
            if resolution:
                result_lines.append(resolution + "\n")
            block_idx += 1
        else:
            result_lines.append(lines[i] if lines[i].endswith("\n") else lines[i] + "\n")
            i += 1

    try:
        Path(file_path).write_text("".join(result_lines), encoding="utf-8")
        return True
    except OSError:
        return False
