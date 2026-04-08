"""
Coverage Optimizer — suggest tests to maximize coverage;
prioritize high-risk uncovered code; effort estimation.

Pure stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from lidco.coverage.analyzer import (
    AnalysisResult,
    CoverageGap,
    FileRiskAssessment,
    RiskLevel,
    UncoveredFunction,
)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TestSuggestion:
    """A suggested test to improve coverage."""

    file_path: str
    target: str  # function name or line range
    description: str
    priority: int  # 1 = highest
    estimated_effort: str  # "low", "medium", "high"
    expected_line_gain: int


@dataclass(frozen=True)
class OptimizationPlan:
    """Full plan of suggested tests ordered by priority."""

    suggestions: tuple[TestSuggestion, ...] = ()
    total_expected_gain: int = 0
    current_line_rate: float = 0.0
    projected_line_rate: float = 0.0

    @property
    def suggestion_count(self) -> int:
        return len(self.suggestions)


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------

_RISK_PRIORITY = {
    RiskLevel.CRITICAL: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.MEDIUM: 3,
    RiskLevel.LOW: 4,
}

_EFFORT_MAP = {
    "small": "low",     # <= 5 lines
    "medium": "medium", # 6-20 lines
    "large": "high",    # > 20 lines
}


class CoverageOptimizer:
    """Suggest tests to maximize coverage improvement."""

    def __init__(self, *, max_suggestions: int = 50) -> None:
        self._max_suggestions = max_suggestions

    def optimize(self, analysis: AnalysisResult) -> OptimizationPlan:
        """Generate an optimization plan from an analysis result."""
        suggestions: list[TestSuggestion] = []

        # 1. Suggest tests for uncovered functions
        for uf in analysis.uncovered_functions:
            size = uf.end_line - uf.start_line + 1
            effort = self._estimate_effort(size)
            priority = _RISK_PRIORITY.get(uf.risk, 4)
            suggestions.append(
                TestSuggestion(
                    file_path=uf.file_path,
                    target=uf.name,
                    description=f"Add unit test for function '{uf.name}' "
                    f"(lines {uf.start_line}-{uf.end_line})",
                    priority=priority,
                    estimated_effort=effort,
                    expected_line_gain=size,
                )
            )

        # 2. Suggest tests for large coverage gaps
        for gap in analysis.gaps:
            if gap.line_count < 2:
                continue
            effort = self._estimate_effort(gap.line_count)
            priority = _RISK_PRIORITY.get(gap.risk, 4)
            suggestions.append(
                TestSuggestion(
                    file_path=gap.file_path,
                    target=f"lines {gap.start_line}-{gap.end_line}",
                    description=f"Cover gap at {gap.file_path}:{gap.start_line}-"
                    f"{gap.end_line} ({gap.line_count} lines)",
                    priority=priority,
                    estimated_effort=effort,
                    expected_line_gain=gap.line_count,
                )
            )

        # 3. Suggest tests for partial branches
        for pb in analysis.partial_branches:
            uncovered = pb.total_branches - pb.covered_branches
            suggestions.append(
                TestSuggestion(
                    file_path=pb.file_path,
                    target=f"branch at line {pb.line_number}",
                    description=f"Cover {uncovered} uncovered branch(es) at "
                    f"{pb.file_path}:{pb.line_number}",
                    priority=_RISK_PRIORITY.get(pb.risk, 3),
                    estimated_effort="low",
                    expected_line_gain=uncovered,
                )
            )

        # Sort by priority (asc) then expected gain (desc)
        suggestions.sort(key=lambda s: (s.priority, -s.expected_line_gain))
        suggestions = suggestions[: self._max_suggestions]

        total_gain = sum(s.expected_line_gain for s in suggestions)

        # Project new rate
        current_covered = 0
        current_total = 0
        for fa in analysis.file_assessments:
            current_covered += int(fa.line_rate * 100)  # approximate
            current_total += 100

        projected = analysis.overall_line_rate
        if current_total > 0:
            # rough projection: gain lines / total lines
            total_lines = sum(
                fa.line_rate * 100 + (1 - fa.line_rate) * 100
                for fa in analysis.file_assessments
            )
            if total_lines > 0:
                added_rate = total_gain / total_lines
                projected = min(1.0, analysis.overall_line_rate + added_rate)

        return OptimizationPlan(
            suggestions=tuple(suggestions),
            total_expected_gain=total_gain,
            current_line_rate=analysis.overall_line_rate,
            projected_line_rate=round(projected, 4),
        )

    def prioritize_files(
        self, analysis: AnalysisResult, *, top_n: int = 10
    ) -> list[FileRiskAssessment]:
        """Return the top-N files most in need of additional tests.

        Sorted by risk (critical first) then lowest line rate.
        """
        ranked = sorted(
            analysis.file_assessments,
            key=lambda fa: (_RISK_PRIORITY.get(fa.risk, 4), fa.line_rate),
        )
        return ranked[:top_n]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_effort(line_count: int) -> str:
        if line_count <= 5:
            return "low"
        if line_count <= 20:
            return "medium"
        return "high"
