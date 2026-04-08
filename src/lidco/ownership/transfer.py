"""
Knowledge Transfer — plan transfers, identify critical paths, suggest pairing.

Pure stdlib, no external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lidco.ownership.analyzer import KnowledgeSilo, OwnershipReport


@dataclass(frozen=True)
class CriticalPath:
    """A directory where knowledge loss risk is highest."""

    path: str
    sole_owner: str
    total_lines: int
    risk_score: float  # 0.0–1.0


@dataclass(frozen=True)
class PairingSuggestion:
    """A suggested pair-programming session for knowledge transfer."""

    expert: str
    learner: str
    path: str
    reason: str


@dataclass(frozen=True)
class DocGap:
    """A directory lacking documentation."""

    directory: str
    file_count: int
    has_readme: bool
    has_docstrings: bool


@dataclass
class TransferPlan:
    """Full knowledge transfer plan."""

    critical_paths: list[CriticalPath] = field(default_factory=list)
    pairing_suggestions: list[PairingSuggestion] = field(default_factory=list)
    doc_gaps: list[DocGap] = field(default_factory=list)
    priority_order: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "critical_path_count": len(self.critical_paths),
            "pairing_suggestion_count": len(self.pairing_suggestions),
            "doc_gap_count": len(self.doc_gaps),
        }


class KnowledgeTransferPlanner:
    """Plan knowledge transfer based on ownership analysis."""

    def __init__(
        self,
        risk_threshold: float = 0.70,
        team_members: list[str] | None = None,
        doc_extensions: list[str] | None = None,
    ) -> None:
        self._risk_threshold = risk_threshold
        self._team_members = list(team_members) if team_members else []
        self._doc_extensions = doc_extensions or [
            "README.md", "README.rst", "readme.md",
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plan(
        self,
        report: OwnershipReport,
        directory_files: dict[str, list[str]] | None = None,
    ) -> TransferPlan:
        """Generate a full transfer plan from an ownership report."""
        critical = self._identify_critical_paths(report.knowledge_silos)
        pairings = self._suggest_pairings(critical)
        gaps = self._find_doc_gaps(directory_files or {})
        priority = self._prioritize(critical)

        return TransferPlan(
            critical_paths=critical,
            pairing_suggestions=pairings,
            doc_gaps=gaps,
            priority_order=priority,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _identify_critical_paths(
        self, silos: list[KnowledgeSilo],
    ) -> list[CriticalPath]:
        paths: list[CriticalPath] = []
        for silo in silos:
            risk = self._compute_risk(silo)
            if risk >= self._risk_threshold:
                paths.append(
                    CriticalPath(
                        path=silo.path,
                        sole_owner=silo.sole_owner,
                        total_lines=silo.total_lines,
                        risk_score=risk,
                    )
                )
        return sorted(paths, key=lambda c: c.risk_score, reverse=True)

    @staticmethod
    def _compute_risk(silo: KnowledgeSilo) -> float:
        """Risk = ownership_fraction * size_factor (capped at 1.0)."""
        size_factor = min(silo.total_lines / 500, 1.0)
        return min(silo.ownership_fraction * (0.5 + 0.5 * size_factor), 1.0)

    def _suggest_pairings(
        self, critical: list[CriticalPath],
    ) -> list[PairingSuggestion]:
        suggestions: list[PairingSuggestion] = []
        learners = [m for m in self._team_members]

        for cp in critical:
            available = [l for l in learners if l != cp.sole_owner]
            if not available:
                continue
            # Pick the first available as learner (round-robin style)
            learner = available[0]
            suggestions.append(
                PairingSuggestion(
                    expert=cp.sole_owner,
                    learner=learner,
                    path=cp.path,
                    reason=f"risk={cp.risk_score:.2f}, {cp.total_lines} lines",
                )
            )
            # Rotate learners so we spread the load
            if learner in learners:
                learners = [l for l in learners if l != learner] + [learner]

        return suggestions

    def _find_doc_gaps(
        self, directory_files: dict[str, list[str]],
    ) -> list[DocGap]:
        gaps: list[DocGap] = []
        for directory, files in sorted(directory_files.items()):
            has_readme = any(
                f.split("/")[-1] in self._doc_extensions
                or f.split("\\")[-1] in self._doc_extensions
                for f in files
            )
            has_docs = any(
                f.endswith(".py") for f in files
            )  # proxy: if there's code, check docstrings
            gaps.append(
                DocGap(
                    directory=directory,
                    file_count=len(files),
                    has_readme=has_readme,
                    has_docstrings=has_docs,
                )
            )
        return [g for g in gaps if not g.has_readme]

    @staticmethod
    def _prioritize(critical: list[CriticalPath]) -> list[str]:
        """Return directories sorted by priority (highest risk first)."""
        return [cp.path for cp in sorted(
            critical, key=lambda c: c.risk_score, reverse=True,
        )]
