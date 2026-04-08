"""
Coverage Analyzer — analyze coverage gaps; untested functions;
partially covered branches; risk assessment.

Pure stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from lidco.coverage.collector import (
    BranchCoverage,
    CoverageSnapshot,
    FileCoverage,
    FunctionCoverage,
)


# ---------------------------------------------------------------------------
# Risk levels
# ---------------------------------------------------------------------------

class RiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Analysis results
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UncoveredFunction:
    """A function with zero test hits."""

    file_path: str
    name: str
    start_line: int
    end_line: int
    risk: str = RiskLevel.MEDIUM


@dataclass(frozen=True)
class PartiallyCoveredBranch:
    """A branch point where some paths are untested."""

    file_path: str
    line_number: int
    covered_branches: int
    total_branches: int
    risk: str = RiskLevel.MEDIUM


@dataclass(frozen=True)
class CoverageGap:
    """A contiguous range of uncovered lines."""

    file_path: str
    start_line: int
    end_line: int
    line_count: int
    risk: str = RiskLevel.LOW


@dataclass(frozen=True)
class FileRiskAssessment:
    """Risk assessment for a single file."""

    path: str
    line_rate: float
    function_rate: float
    branch_rate: float
    risk: str
    uncovered_functions: tuple[UncoveredFunction, ...] = ()
    gaps: tuple[CoverageGap, ...] = ()
    partial_branches: tuple[PartiallyCoveredBranch, ...] = ()


@dataclass(frozen=True)
class AnalysisResult:
    """Complete analysis across all files."""

    overall_line_rate: float
    overall_function_rate: float
    overall_branch_rate: float
    overall_risk: str
    file_assessments: tuple[FileRiskAssessment, ...] = ()
    uncovered_functions: tuple[UncoveredFunction, ...] = ()
    gaps: tuple[CoverageGap, ...] = ()
    partial_branches: tuple[PartiallyCoveredBranch, ...] = ()


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class CoverageAnalyzer:
    """Analyze a coverage snapshot for gaps, risk, and untested code."""

    def __init__(self, *, risk_thresholds: dict[str, float] | None = None) -> None:
        self._thresholds = risk_thresholds or {
            "critical": 0.3,
            "high": 0.5,
            "medium": 0.7,
        }

    def analyze(self, snapshot: CoverageSnapshot) -> AnalysisResult:
        """Run full analysis on a snapshot."""
        all_uncovered: list[UncoveredFunction] = []
        all_gaps: list[CoverageGap] = []
        all_partial: list[PartiallyCoveredBranch] = []
        assessments: list[FileRiskAssessment] = []

        for fc in snapshot.files:
            uncovered = self._find_uncovered_functions(fc)
            gaps = self._find_coverage_gaps(fc)
            partial = self._find_partial_branches(fc)
            risk = self._assess_risk(fc.line_rate)

            all_uncovered.extend(uncovered)
            all_gaps.extend(gaps)
            all_partial.extend(partial)

            assessments.append(
                FileRiskAssessment(
                    path=fc.path,
                    line_rate=fc.line_rate,
                    function_rate=fc.function_rate,
                    branch_rate=fc.branch_rate,
                    risk=risk,
                    uncovered_functions=tuple(uncovered),
                    gaps=tuple(gaps),
                    partial_branches=tuple(partial),
                )
            )

        overall_risk = self._assess_risk(snapshot.line_rate)
        overall_fn_rate = 0.0
        total_fns = snapshot.total_functions
        if total_fns:
            overall_fn_rate = snapshot.covered_functions / total_fns
        overall_br_rate = 0.0
        total_br = snapshot.total_branches
        if total_br:
            overall_br_rate = snapshot.covered_branches / total_br

        return AnalysisResult(
            overall_line_rate=snapshot.line_rate,
            overall_function_rate=overall_fn_rate,
            overall_branch_rate=overall_br_rate,
            overall_risk=overall_risk,
            file_assessments=tuple(assessments),
            uncovered_functions=tuple(all_uncovered),
            gaps=tuple(all_gaps),
            partial_branches=tuple(all_partial),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _assess_risk(self, rate: float) -> str:
        if rate < self._thresholds["critical"]:
            return RiskLevel.CRITICAL
        if rate < self._thresholds["high"]:
            return RiskLevel.HIGH
        if rate < self._thresholds["medium"]:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _find_uncovered_functions(self, fc: FileCoverage) -> list[UncoveredFunction]:
        result: list[UncoveredFunction] = []
        for fn in fc.functions:
            if fn.hits == 0:
                size = fn.end_line - fn.start_line + 1
                risk = RiskLevel.HIGH if size > 20 else RiskLevel.MEDIUM
                result.append(
                    UncoveredFunction(
                        file_path=fc.path,
                        name=fn.name,
                        start_line=fn.start_line,
                        end_line=fn.end_line,
                        risk=risk,
                    )
                )
        return result

    def _find_coverage_gaps(self, fc: FileCoverage) -> list[CoverageGap]:
        """Find contiguous ranges of uncovered lines."""
        uncovered = sorted(ln.line_number for ln in fc.lines if ln.hits == 0)
        if not uncovered:
            return []

        gaps: list[CoverageGap] = []
        start = uncovered[0]
        prev = uncovered[0]

        for ln in uncovered[1:]:
            if ln == prev + 1:
                prev = ln
            else:
                count = prev - start + 1
                risk = RiskLevel.HIGH if count > 10 else RiskLevel.MEDIUM if count > 3 else RiskLevel.LOW
                gaps.append(
                    CoverageGap(
                        file_path=fc.path,
                        start_line=start,
                        end_line=prev,
                        line_count=count,
                        risk=risk,
                    )
                )
                start = ln
                prev = ln

        # Final gap
        count = prev - start + 1
        risk = RiskLevel.HIGH if count > 10 else RiskLevel.MEDIUM if count > 3 else RiskLevel.LOW
        gaps.append(
            CoverageGap(
                file_path=fc.path,
                start_line=start,
                end_line=prev,
                line_count=count,
                risk=risk,
            )
        )
        return gaps

    def _find_partial_branches(self, fc: FileCoverage) -> list[PartiallyCoveredBranch]:
        """Group branches by line and find partially covered branch points."""
        branch_map: dict[int, list[BranchCoverage]] = {}
        for br in fc.branches:
            branch_map.setdefault(br.line_number, []).append(br)

        result: list[PartiallyCoveredBranch] = []
        for line_no, brs in sorted(branch_map.items()):
            covered = sum(1 for b in brs if b.hits > 0)
            total = len(brs)
            if 0 < covered < total:
                risk = RiskLevel.HIGH if covered < total // 2 else RiskLevel.MEDIUM
                result.append(
                    PartiallyCoveredBranch(
                        file_path=fc.path,
                        line_number=line_no,
                        covered_branches=covered,
                        total_branches=total,
                        risk=risk,
                    )
                )
        return result
