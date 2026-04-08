"""
Ownership Analyzer — analyze code ownership distribution.

Bus factor, knowledge silos, orphaned files, coverage gaps.
Pure stdlib, no external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lidco.ownership.generator import BlameEntry


@dataclass(frozen=True)
class BusFactorResult:
    """Bus factor analysis for a directory or repository."""

    path: str
    bus_factor: int
    top_contributors: list[tuple[str, int]]
    total_lines: int


@dataclass(frozen=True)
class KnowledgeSilo:
    """A path where a single author owns the vast majority of code."""

    path: str
    sole_owner: str
    ownership_fraction: float
    total_lines: int


@dataclass(frozen=True)
class OrphanedFile:
    """A tracked file with zero blame data (e.g. binary or empty)."""

    file_path: str
    reason: str


@dataclass(frozen=True)
class CoverageGap:
    """A directory with no CODEOWNERS coverage."""

    directory: str
    file_count: int


@dataclass
class OwnershipReport:
    """Full ownership analysis report."""

    bus_factors: list[BusFactorResult] = field(default_factory=list)
    knowledge_silos: list[KnowledgeSilo] = field(default_factory=list)
    orphaned_files: list[OrphanedFile] = field(default_factory=list)
    coverage_gaps: list[CoverageGap] = field(default_factory=list)
    overall_bus_factor: int = 0

    def summary(self) -> dict[str, Any]:
        """Return a plain-dict summary for display."""
        return {
            "overall_bus_factor": self.overall_bus_factor,
            "silo_count": len(self.knowledge_silos),
            "orphaned_count": len(self.orphaned_files),
            "gap_count": len(self.coverage_gaps),
            "directory_count": len(self.bus_factors),
        }


class OwnershipAnalyzer:
    """Analyze code ownership from blame data."""

    def __init__(
        self,
        silo_threshold: float = 0.80,
        bus_factor_threshold: float = 0.80,
    ) -> None:
        self._silo_threshold = silo_threshold
        self._bus_factor_threshold = bus_factor_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        blame_entries: list[BlameEntry],
        codeowners_patterns: list[str] | None = None,
        tracked_files: list[str] | None = None,
    ) -> OwnershipReport:
        """Run full ownership analysis and return a report."""
        dir_authors = self._group_by_directory(blame_entries)
        bus_factors = self._compute_bus_factors(dir_authors)
        silos = self._find_silos(dir_authors)
        orphaned = self._find_orphaned(blame_entries, tracked_files)
        gaps = self._find_coverage_gaps(
            dir_authors, codeowners_patterns or [],
        )
        overall = self._overall_bus_factor(blame_entries)

        return OwnershipReport(
            bus_factors=bus_factors,
            knowledge_silos=silos,
            orphaned_files=orphaned,
            coverage_gaps=gaps,
            overall_bus_factor=overall,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _group_by_directory(
        entries: list[BlameEntry],
    ) -> dict[str, dict[str, int]]:
        from pathlib import Path as _P

        result: dict[str, dict[str, int]] = {}
        for e in entries:
            parent = str(_P(e.file_path).parent).replace("\\", "/")
            if parent not in result:
                result[parent] = {}
            result[parent][e.author] = result[parent].get(e.author, 0) + e.lines
        return result

    def _compute_bus_factors(
        self, dir_authors: dict[str, dict[str, int]]
    ) -> list[BusFactorResult]:
        results: list[BusFactorResult] = []
        for directory, authors in sorted(dir_authors.items()):
            total = sum(authors.values())
            if total == 0:
                results.append(
                    BusFactorResult(
                        path=directory, bus_factor=0,
                        top_contributors=[], total_lines=0,
                    )
                )
                continue

            sorted_authors = sorted(
                authors.items(), key=lambda x: x[1], reverse=True,
            )
            cumulative = 0
            bus_factor = 0
            for _author, lines in sorted_authors:
                cumulative += lines
                bus_factor += 1
                if cumulative / total >= self._bus_factor_threshold:
                    break

            results.append(
                BusFactorResult(
                    path=directory,
                    bus_factor=bus_factor,
                    top_contributors=sorted_authors[:5],
                    total_lines=total,
                )
            )
        return results

    def _find_silos(
        self, dir_authors: dict[str, dict[str, int]]
    ) -> list[KnowledgeSilo]:
        silos: list[KnowledgeSilo] = []
        for directory, authors in sorted(dir_authors.items()):
            total = sum(authors.values())
            if total == 0:
                continue
            top_author, top_lines = max(
                authors.items(), key=lambda x: x[1],
            )
            fraction = top_lines / total
            if fraction >= self._silo_threshold:
                silos.append(
                    KnowledgeSilo(
                        path=directory,
                        sole_owner=top_author,
                        ownership_fraction=fraction,
                        total_lines=total,
                    )
                )
        return silos

    @staticmethod
    def _find_orphaned(
        blame_entries: list[BlameEntry],
        tracked_files: list[str] | None,
    ) -> list[OrphanedFile]:
        if tracked_files is None:
            return []
        blamed_files = {e.file_path for e in blame_entries}
        orphaned: list[OrphanedFile] = []
        for f in sorted(tracked_files):
            if f not in blamed_files:
                orphaned.append(
                    OrphanedFile(file_path=f, reason="no blame data")
                )
        return orphaned

    @staticmethod
    def _find_coverage_gaps(
        dir_authors: dict[str, dict[str, int]],
        codeowners_patterns: list[str],
    ) -> list[CoverageGap]:
        if not codeowners_patterns:
            # Every directory is a gap if there are no patterns
            return [
                CoverageGap(directory=d, file_count=len(authors))
                for d, authors in sorted(dir_authors.items())
            ]

        normalized = {p.strip().rstrip("/") for p in codeowners_patterns}
        gaps: list[CoverageGap] = []
        for directory, authors in sorted(dir_authors.items()):
            norm_dir = f"/{directory}" if not directory.startswith("/") else directory
            covered = any(
                norm_dir.startswith(pat) or pat == "*"
                for pat in normalized
            )
            if not covered:
                gaps.append(
                    CoverageGap(directory=directory, file_count=len(authors))
                )
        return gaps

    def _overall_bus_factor(self, entries: list[BlameEntry]) -> int:
        global_authors: dict[str, int] = {}
        for e in entries:
            global_authors[e.author] = global_authors.get(e.author, 0) + e.lines
        total = sum(global_authors.values())
        if total == 0:
            return 0
        sorted_a = sorted(global_authors.items(), key=lambda x: x[1], reverse=True)
        cumulative = 0
        factor = 0
        for _author, lines in sorted_a:
            cumulative += lines
            factor += 1
            if cumulative / total >= self._bus_factor_threshold:
                break
        return factor
