"""Import dependency graph built from the SQLite project index.

Provides ``DependencyGraph`` — a lightweight in-memory graph of file-level
import relationships derived from the ``imports`` table.  Used by
``IndexContextEnricher`` to surface related files when an agent is working on
a specific file.

Key operations:
    graph.get_dependencies(path)  → files that *path* imports
    graph.get_dependents(path)    → files that import *path*
    graph.get_related(path, limit) → top-N related files (both directions)
    graph.find_cycles()           → all circular import chains
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass

from lidco.index.db import IndexDatabase
from lidco.index.schema import FileRecord

logger = logging.getLogger(__name__)


def _min_rotation(cycle: list[str]) -> tuple[str, ...]:
    """Return the lexicographically smallest rotation of *cycle*."""
    n = len(cycle)
    tup = tuple(cycle)
    min_rot = tup
    for i in range(1, n):
        rot = tup[i:] + tup[:i]
        if rot < min_rot:
            min_rot = rot
    return min_rot


@dataclass(frozen=True)
class RelatedFile:
    """A file related to a given source by import dependencies."""

    record: FileRecord
    relation: str  # "imports" | "imported_by"
    distance: int  # 1 = direct, 2 = transitive (future)


class DependencyGraph:
    """In-memory import graph built from ``IndexDatabase``.

    The graph is built lazily on first use and is intended to be short-lived
    (per-request), since the underlying index can change between sessions.

    Parameters
    ----------
    db:
        Open ``IndexDatabase`` instance.  The caller retains ownership.
    """

    def __init__(self, db: IndexDatabase) -> None:
        self._db = db
        # path → set of paths this file imports (resolved paths only)
        self._imports: dict[str, set[str]] = defaultdict(set)
        # path → set of paths that import this file
        self._imported_by: dict[str, set[str]] = defaultdict(set)
        # path → FileRecord (lazy cache)
        self._file_cache: dict[str, FileRecord] = {}
        self._built = False

    # ── Graph construction ────────────────────────────────────────────────────

    def _ensure_built(self) -> None:
        """Build the adjacency lists from the DB on first call."""
        if self._built:
            return

        # Load all files for fast id→path lookup
        all_files = self._db.list_all_files()
        id_to_path: dict[int, str] = {}
        for f in all_files:
            id_to_path[f.id] = f.path
            self._file_cache[f.path] = f

        # Walk every file's imports and populate both adjacency lists
        for f in all_files:
            for imp in self._db.query_imports_for_file(f.id):
                resolved = imp.resolved_path
                if not resolved:
                    continue
                # resolved_path may be absolute or relative — normalise to
                # relative (we match against paths stored in the index)
                target = self._normalise(resolved, id_to_path)
                if target and target != f.path:
                    self._imports[f.path].add(target)
                    self._imported_by[target].add(f.path)

        self._built = True

    def _normalise(self, resolved_path: str, id_to_path: dict[int, str]) -> str:
        """Return the index-relative path matching resolved_path, or ''."""
        # Try exact match first
        if resolved_path in self._file_cache:
            return resolved_path
        # Try suffix match: resolved may be absolute, index stores relative
        for path in self._file_cache:
            if resolved_path.endswith(path) or path.endswith(resolved_path):
                return path
        return ""

    # ── Public API ────────────────────────────────────────────────────────────

    def get_dependencies(self, file_path: str) -> list[FileRecord]:
        """Return files that *file_path* imports (files it depends on)."""
        self._ensure_built()
        return self._resolve_paths(self._imports.get(file_path, set()))

    def get_dependents(self, file_path: str) -> list[FileRecord]:
        """Return files that import *file_path* (files that depend on it)."""
        self._ensure_built()
        return self._resolve_paths(self._imported_by.get(file_path, set()))

    def get_related(
        self,
        file_path: str,
        limit: int = 5,
    ) -> list[RelatedFile]:
        """Return up to *limit* files related to *file_path* by imports.

        Priority order:
        1. Files that import *file_path* (dependents) — they are likely
           consumers that need to know about changes.
        2. Files that *file_path* imports (dependencies) — related context.

        Each entry is distinct; if a file appears in both directions, it is
        listed once as "imported_by" (higher priority).
        """
        self._ensure_built()

        seen: set[str] = {file_path}
        result: list[RelatedFile] = []

        # Dependents first
        for rec in self.get_dependents(file_path):
            if rec.path not in seen:
                seen.add(rec.path)
                result.append(RelatedFile(record=rec, relation="imported_by", distance=1))
            if len(result) >= limit:
                return result

        # Dependencies second
        for rec in self.get_dependencies(file_path):
            if rec.path not in seen:
                seen.add(rec.path)
                result.append(RelatedFile(record=rec, relation="imports", distance=1))
            if len(result) >= limit:
                return result

        return result

    def find_cycles(self) -> list[list[str]]:
        """Return all circular import chains in the dependency graph.

        Uses iterative DFS to avoid hitting Python's recursion limit on large
        codebases.  Each returned list is a cycle expressed as an ordered path
        of file names where the last entry imports the first.  Cycles are
        deduplicated by normalising to the lexicographically smallest rotation,
        so ``[A, B, C]`` and ``[B, C, A]`` are returned as a single entry.
        """
        self._ensure_built()

        visited: set[str] = set()
        cycles: set[tuple[str, ...]] = set()

        def _dfs(start: str) -> None:
            # Iterative DFS with explicit call stack
            # Each frame: (node, iterator-over-neighbours, path-so-far, in_stack)
            stack: list[tuple[str, list[str], int]] = [(start, [start], 0)]
            in_stack: dict[str, int] = {start: 0}  # node → depth

            while stack:
                node, path, depth = stack[-1]
                neighbours = sorted(self._imports.get(node, set()))

                pushed = False
                for nb in neighbours:
                    if nb in in_stack:
                        # Back edge → cycle found
                        cycle_start = in_stack[nb]
                        cycle = path[cycle_start:]
                        cycles.add(_min_rotation(cycle))
                    elif nb not in visited:
                        visited.add(nb)
                        new_path = path + [nb]
                        in_stack[nb] = len(path)
                        stack.append((nb, new_path, depth + 1))
                        pushed = True
                        break

                if not pushed:
                    stack.pop()
                    if path:
                        in_stack.pop(path[-1], None)

        for node in sorted(self._imports.keys()):
            if node not in visited:
                visited.add(node)
                _dfs(node)

        return sorted([list(c) for c in cycles])

    def _resolve_paths(self, paths: set[str]) -> list[FileRecord]:
        """Return FileRecords for a set of paths, sorted alphabetically."""
        result: list[FileRecord] = []
        for path in sorted(paths):
            rec = self._file_cache.get(path)
            if rec is None:
                rec = self._db.get_file_by_path(path)
            if rec is not None:
                result.append(rec)
        return result
