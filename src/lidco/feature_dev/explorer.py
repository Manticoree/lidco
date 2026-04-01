"""Code Explorer Agent — analyse codebase structure for feature development.

All data classes are frozen (immutable).  Methods return new objects rather
than mutating state.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SimilarFeature:
    """A feature in the codebase that resembles the target description."""

    name: str
    path: str
    similarity: float
    description: str


@dataclass(frozen=True)
class ExplorationResult:
    """Result of exploring a directory tree."""

    root: str
    files_found: int
    focus_hits: tuple[str, ...]
    summary: str


@dataclass(frozen=True)
class ExecutionFlow:
    """Simplified execution trace from an entry point."""

    entry_point: str
    steps: tuple[str, ...]
    calls: tuple[str, ...]


@dataclass(frozen=True)
class ArchitectureMap:
    """High-level architecture view of a path."""

    root: str
    modules: tuple[str, ...]
    dependencies: tuple[str, ...]
    summary: str


class CodeExplorerAgent:
    """Lightweight code exploration agent (stdlib only).

    Walks files, matches focus areas, and produces immutable result objects.
    Real LLM integration would subclass or compose with this.
    """

    def __init__(self, *, max_depth: int = 5) -> None:
        self._max_depth = max_depth

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def explore(
        self,
        path: str,
        focus_areas: tuple[str, ...] = (),
    ) -> ExplorationResult:
        """Walk *path* and identify files matching *focus_areas*."""
        if not os.path.isdir(path):
            return ExplorationResult(
                root=path,
                files_found=0,
                focus_hits=(),
                summary=f"Path '{path}' is not a directory",
            )

        files: list[str] = []
        hits: list[str] = []
        for dirpath, _dirs, filenames in os.walk(path):
            depth = dirpath.replace(path, "").count(os.sep)
            if depth > self._max_depth:
                continue
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                files.append(fp)
                if focus_areas and any(area.lower() in fn.lower() for area in focus_areas):
                    hits.append(fp)

        return ExplorationResult(
            root=path,
            files_found=len(files),
            focus_hits=tuple(hits),
            summary=f"Explored {len(files)} files, {len(hits)} focus hits",
        )

    def trace_execution(self, entry_point: str) -> ExecutionFlow:
        """Return a simplified execution flow from *entry_point*.

        This is a stub — real implementation would use AST analysis.
        """
        if not os.path.isfile(entry_point):
            return ExecutionFlow(
                entry_point=entry_point,
                steps=(),
                calls=(),
            )

        lines: list[str] = []
        calls: list[str] = []
        try:
            with open(entry_point, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    stripped = line.strip()
                    if stripped.startswith("def ") or stripped.startswith("class "):
                        lines.append(stripped.split("(")[0])
                    if "(" in stripped and not stripped.startswith(("#", "def ", "class ")):
                        name = stripped.split("(")[0].strip().split(".")[-1]
                        if name.isidentifier():
                            calls.append(name)
        except OSError:
            pass

        return ExecutionFlow(
            entry_point=entry_point,
            steps=tuple(lines),
            calls=tuple(dict.fromkeys(calls)),  # dedupe, preserve order
        )

    def map_architecture(self, path: str) -> ArchitectureMap:
        """Build a high-level architecture map of *path*."""
        if not os.path.isdir(path):
            return ArchitectureMap(
                root=path,
                modules=(),
                dependencies=(),
                summary=f"Path '{path}' is not a directory",
            )

        modules: list[str] = []
        deps: set[str] = set()
        for entry in sorted(os.listdir(path)):
            full = os.path.join(path, entry)
            if os.path.isdir(full) and not entry.startswith((".", "__")):
                modules.append(entry)
            if entry == "requirements.txt":
                try:
                    with open(full, encoding="utf-8", errors="replace") as fh:
                        for line in fh:
                            pkg = line.strip().split("==")[0].split(">=")[0].strip()
                            if pkg and not pkg.startswith("#"):
                                deps.add(pkg)
                except OSError:
                    pass

        return ArchitectureMap(
            root=path,
            modules=tuple(modules),
            dependencies=tuple(sorted(deps)),
            summary=f"{len(modules)} modules, {len(deps)} dependencies",
        )

    def find_similar_features(
        self,
        description: str,
        path: str,
    ) -> tuple[SimilarFeature, ...]:
        """Find features in *path* similar to *description* (keyword match)."""
        if not os.path.isdir(path):
            return ()

        keywords = {w.lower() for w in description.split() if len(w) > 2}
        if not keywords:
            return ()

        results: list[SimilarFeature] = []
        for entry in sorted(os.listdir(path)):
            full = os.path.join(path, entry)
            if not os.path.isdir(full):
                continue
            name_lower = entry.lower().replace("_", " ").replace("-", " ")
            name_words = set(name_lower.split())
            overlap = keywords & name_words
            if overlap:
                score = len(overlap) / len(keywords)
                results.append(SimilarFeature(
                    name=entry,
                    path=full,
                    similarity=round(score, 2),
                    description=f"Matches keywords: {', '.join(sorted(overlap))}",
                ))

        return tuple(sorted(results, key=lambda s: s.similarity, reverse=True))


__all__ = [
    "CodeExplorerAgent",
    "ExplorationResult",
    "ExecutionFlow",
    "ArchitectureMap",
    "SimilarFeature",
]
