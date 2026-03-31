"""Multi-language repo map — Task 929."""
from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from typing import Callable

from lidco.ast.universal_extractor import ExtractedSymbol, UniversalExtractor


_DEFAULT_EXCLUDES = {
    "node_modules",
    "__pycache__",
    ".git",
    ".hg",
    ".svn",
    ".tox",
    ".venv",
    "venv",
    "env",
    ".env",
    "dist",
    "build",
    ".eggs",
    "*.egg-info",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".next",
    "coverage",
    ".coverage",
    "target",
}


@dataclass
class RepoMapEntry:
    """One file in the repo map."""

    file_path: str
    language: str
    symbols: list[ExtractedSymbol] = field(default_factory=list)
    line_count: int = 0


WalkFn = Callable[[str], list[str]]
ReadFn = Callable[[str], str]


def _default_walk(root: str) -> list[str]:
    """Walk directory, returning relative file paths."""
    result: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # prune excluded dirs in-place
        dirnames[:] = [
            d for d in dirnames
            if d not in _DEFAULT_EXCLUDES and not d.startswith(".")
        ]
        for f in filenames:
            rel = os.path.relpath(os.path.join(dirpath, f), root)
            result.append(rel.replace("\\", "/"))
    return result


def _default_read(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


class MultiLanguageRepoMap:
    """Build a symbol map of a repository across all languages."""

    def __init__(
        self,
        extractor: UniversalExtractor,
        max_files: int = 500,
        walk_fn: WalkFn | None = None,
        read_fn: ReadFn | None = None,
    ) -> None:
        self._extractor = extractor
        self._max_files = max_files
        self._walk_fn = walk_fn or _default_walk
        self._read_fn = read_fn or _default_read

    def build(
        self,
        root_dir: str,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> list[RepoMapEntry]:
        """Build repo map entries for *root_dir*."""
        files = self._walk_fn(root_dir)
        entries: list[RepoMapEntry] = []

        for rel_path in files:
            if len(entries) >= self._max_files:
                break

            if include_patterns:
                if not any(fnmatch.fnmatch(rel_path, p) for p in include_patterns):
                    continue

            if exclude_patterns:
                if any(fnmatch.fnmatch(rel_path, p) for p in exclude_patterns):
                    continue

            lang = self._extractor._parser.detect_language(rel_path)
            if lang is None:
                continue

            abs_path = os.path.join(root_dir, rel_path)
            try:
                source = self._read_fn(abs_path)
            except Exception:
                continue

            symbols = self._extractor.extract(source, lang)
            line_count = source.count("\n") + (1 if source and not source.endswith("\n") else 0)
            entries.append(
                RepoMapEntry(
                    file_path=rel_path,
                    language=lang,
                    symbols=symbols,
                    line_count=line_count,
                )
            )

        return entries

    def format_map(
        self, entries: list[RepoMapEntry], style: str = "tree"
    ) -> str:
        """Format entries as a human-readable text tree."""
        if not entries:
            return "(empty repo map)"

        lines: list[str] = []
        for entry in entries:
            lines.append(f"{entry.file_path}  ({entry.language}, {entry.line_count} lines)")
            for sym in entry.symbols:
                kind_tag = sym.kind
                end = f"-{sym.end_line}" if sym.end_line else ""
                lines.append(f"  {kind_tag}: {sym.name}  L{sym.line}{end}")
        return "\n".join(lines)

    def search_symbols(
        self, entries: list[RepoMapEntry], query: str
    ) -> list[ExtractedSymbol]:
        """Search for symbols matching *query* (case-insensitive substring)."""
        query_lower = query.lower()
        results: list[ExtractedSymbol] = []
        for entry in entries:
            for sym in entry.symbols:
                if query_lower in sym.name.lower():
                    results.append(sym)
        return results
