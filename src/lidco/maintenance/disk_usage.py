"""Q148: Disk usage analyzer."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, List, Optional

from lidco.ui.status_formatter import StatusFormatter


@dataclass
class UsageEntry:
    path: str
    size_bytes: int
    file_count: int
    is_dir: bool


def _format_size(n: int) -> str:
    """Return a human-friendly size string.

    Delegates to :meth:`StatusFormatter.format_bytes`.
    """
    return StatusFormatter.format_bytes(n)


class DiskUsageAnalyzer:
    """Analyze disk usage of directories."""

    def __init__(
        self,
        *,
        _walk: Optional[Callable] = None,
    ) -> None:
        self._walk = _walk or os.walk

    def analyze(self, root: str) -> list[UsageEntry]:
        """Return a :class:`UsageEntry` per directory under *root*."""
        dir_sizes: dict[str, int] = {}
        dir_counts: dict[str, int] = {}
        for dirpath, _dirs, files in self._walk(root):
            total = 0
            count = 0
            for f in files:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
                count += 1
            dir_sizes[dirpath] = total
            dir_counts[dirpath] = count
        entries: list[UsageEntry] = []
        for d in sorted(dir_sizes):
            entries.append(
                UsageEntry(
                    path=d,
                    size_bytes=dir_sizes[d],
                    file_count=dir_counts[d],
                    is_dir=True,
                )
            )
        return entries

    def largest(self, root: str, n: int = 10) -> list[UsageEntry]:
        """Return top *n* directories by size."""
        entries = self.analyze(root)
        return sorted(entries, key=lambda e: e.size_bytes, reverse=True)[:n]

    @staticmethod
    def by_extension(entries: list[UsageEntry]) -> dict[str, int]:
        """Total bytes per file extension.

        Expects individual file entries (``is_dir=False``).  Directory entries
        derive their extension from the path's trailing component only when
        they look like a file (have a dot after the last separator).
        """
        result: dict[str, int] = {}
        for e in entries:
            _, ext = os.path.splitext(e.path)
            ext = ext if ext else "(no ext)"
            result[ext] = result.get(ext, 0) + e.size_bytes
        return result

    @staticmethod
    def total_size(entries: list[UsageEntry]) -> int:
        return sum(e.size_bytes for e in entries)

    def format_tree(self, entries: list[UsageEntry], max_depth: int = 3) -> str:
        """Return a tree-like display of entries with sizes."""
        if not entries:
            return "(empty)"
        # Determine common root
        paths = [e.path for e in entries]
        common = os.path.commonpath(paths) if len(paths) > 1 else paths[0]
        lines: list[str] = []
        for e in entries:
            rel = os.path.relpath(e.path, common)
            if rel == ".":
                depth = 0
            else:
                depth = rel.replace("\\", "/").count("/") + 1
            if depth > max_depth:
                continue
            indent = "  " * depth
            size_str = _format_size(e.size_bytes)
            label = os.path.basename(e.path) or e.path
            lines.append(f"{indent}{label}/ ({size_str}, {e.file_count} files)")
        return "\n".join(lines) if lines else "(empty)"
