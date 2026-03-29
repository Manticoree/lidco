"""Patch Parser — parse unified diff text into structured PatchFile/PatchHunk objects.

Stdlib only — no external deps.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class PatchHunk:
    """A single @@ hunk from a unified diff."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str] = field(default_factory=list)  # '+'/'-'/' ' prefixed strings


@dataclass
class PatchFile:
    """A per-file section of a unified diff."""
    old_path: str
    new_path: str
    hunks: list[PatchHunk] = field(default_factory=list)

    @property
    def is_new_file(self) -> bool:
        return self.old_path == "/dev/null"

    @property
    def is_deleted(self) -> bool:
        return self.new_path == "/dev/null"


_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class PatchParser:
    """Parse unified diff text into a list of PatchFile objects."""

    def parse(self, text: str) -> list[PatchFile]:
        """Parse a multi-file unified diff."""
        files: list[PatchFile] = []
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            if lines[i].startswith("--- "):
                old_path = _strip_prefix(lines[i][4:])
                i += 1
                if i < len(lines) and lines[i].startswith("+++ "):
                    new_path = _strip_prefix(lines[i][4:])
                    i += 1
                else:
                    continue
                pf = PatchFile(old_path=old_path, new_path=new_path)
                # Parse hunks
                while i < len(lines):
                    m = _HUNK_HEADER.match(lines[i])
                    if m:
                        old_start = int(m.group(1))
                        old_count = int(m.group(2)) if m.group(2) is not None else 1
                        new_start = int(m.group(3))
                        new_count = int(m.group(4)) if m.group(4) is not None else 1
                        hunk = PatchHunk(old_start, old_count, new_start, new_count)
                        i += 1
                        while i < len(lines) and not _HUNK_HEADER.match(lines[i]) and not lines[i].startswith("--- "):
                            hunk.lines.append(lines[i])
                            i += 1
                        pf.hunks.append(hunk)
                    elif lines[i].startswith("--- "):
                        break
                    else:
                        i += 1
                files.append(pf)
            else:
                i += 1
        return files

    def parse_file(self, text: str) -> PatchFile:
        """Parse a single-file diff. Returns first PatchFile found."""
        files = self.parse(text)
        if files:
            return files[0]
        # Fallback: return empty PatchFile
        return PatchFile(old_path="", new_path="")

    def summary(self, files: list[PatchFile]) -> str:
        """Return a summary string: 'N files, +X -Y lines'."""
        added = 0
        removed = 0
        for pf in files:
            for hunk in pf.hunks:
                for line in hunk.lines:
                    if line.startswith("+"):
                        added += 1
                    elif line.startswith("-"):
                        removed += 1
        n = len(files)
        return f"{n} file{'s' if n != 1 else ''}, +{added} -{removed} lines"


def _strip_prefix(path: str) -> str:
    """Remove a/ or b/ prefix from diff paths, and strip timestamps."""
    path = path.strip()
    # Remove timestamp (tab + date at end)
    if "\t" in path:
        path = path.split("\t")[0].strip()
    if path.startswith("a/") or path.startswith("b/"):
        return path[2:]
    return path
