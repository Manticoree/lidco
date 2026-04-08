"""
Coverage Reporter — generate coverage reports in text, JSON, and HTML;
trends over time; team breakdown; threshold enforcement.

Pure stdlib.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Sequence

from lidco.coverage.analyzer import AnalysisResult, FileRiskAssessment
from lidco.coverage.collector import CoverageSnapshot


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ThresholdResult:
    """Result of checking coverage against thresholds."""

    passed: bool
    line_rate: float
    line_threshold: float
    branch_rate: float
    branch_threshold: float
    function_rate: float
    function_threshold: float
    failures: tuple[str, ...] = ()


@dataclass(frozen=True)
class TrendPoint:
    """A single point in a coverage trend."""

    timestamp: str
    line_rate: float
    branch_rate: float
    function_rate: float
    total_lines: int


@dataclass(frozen=True)
class TrendReport:
    """Coverage trend over time."""

    points: tuple[TrendPoint, ...] = ()

    @property
    def direction(self) -> str:
        if len(self.points) < 2:
            return "stable"
        delta = self.points[-1].line_rate - self.points[0].line_rate
        if delta > 0.01:
            return "improving"
        if delta < -0.01:
            return "declining"
        return "stable"

    @property
    def latest_rate(self) -> float:
        if not self.points:
            return 0.0
        return self.points[-1].line_rate


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

class CoverageReporter:
    """Generate coverage reports in multiple formats."""

    def __init__(
        self,
        *,
        line_threshold: float = 0.8,
        branch_threshold: float = 0.7,
        function_threshold: float = 0.8,
    ) -> None:
        self._line_threshold = line_threshold
        self._branch_threshold = branch_threshold
        self._function_threshold = function_threshold

    # ------------------------------------------------------------------
    # Threshold enforcement
    # ------------------------------------------------------------------

    def check_thresholds(self, analysis: AnalysisResult) -> ThresholdResult:
        """Check if coverage meets configured thresholds."""
        failures: list[str] = []

        if analysis.overall_line_rate < self._line_threshold:
            failures.append(
                f"Line coverage {analysis.overall_line_rate:.1%} "
                f"below threshold {self._line_threshold:.1%}"
            )
        if analysis.overall_branch_rate < self._branch_threshold:
            failures.append(
                f"Branch coverage {analysis.overall_branch_rate:.1%} "
                f"below threshold {self._branch_threshold:.1%}"
            )
        if analysis.overall_function_rate < self._function_threshold:
            failures.append(
                f"Function coverage {analysis.overall_function_rate:.1%} "
                f"below threshold {self._function_threshold:.1%}"
            )

        return ThresholdResult(
            passed=len(failures) == 0,
            line_rate=analysis.overall_line_rate,
            line_threshold=self._line_threshold,
            branch_rate=analysis.overall_branch_rate,
            branch_threshold=self._branch_threshold,
            function_rate=analysis.overall_function_rate,
            function_threshold=self._function_threshold,
            failures=tuple(failures),
        )

    # ------------------------------------------------------------------
    # Text report
    # ------------------------------------------------------------------

    def report_text(self, analysis: AnalysisResult) -> str:
        """Generate a plain-text coverage report."""
        lines: list[str] = [
            "Coverage Report",
            "=" * 60,
            f"Overall line rate:     {analysis.overall_line_rate:.1%}",
            f"Overall function rate: {analysis.overall_function_rate:.1%}",
            f"Overall branch rate:   {analysis.overall_branch_rate:.1%}",
            f"Risk level:            {analysis.overall_risk}",
            "",
        ]

        if analysis.file_assessments:
            lines.append("Per-file breakdown:")
            lines.append("-" * 60)
            for fa in analysis.file_assessments:
                lines.append(
                    f"  {fa.path}: lines={fa.line_rate:.0%} "
                    f"funcs={fa.function_rate:.0%} "
                    f"branches={fa.branch_rate:.0%} "
                    f"[{fa.risk}]"
                )

        if analysis.uncovered_functions:
            lines.append("")
            lines.append("Uncovered functions:")
            for uf in analysis.uncovered_functions:
                lines.append(
                    f"  {uf.file_path}:{uf.start_line} {uf.name} [{uf.risk}]"
                )

        if analysis.gaps:
            lines.append("")
            lines.append("Coverage gaps:")
            for g in analysis.gaps:
                lines.append(
                    f"  {g.file_path}:{g.start_line}-{g.end_line} "
                    f"({g.line_count} lines) [{g.risk}]"
                )

        threshold = self.check_thresholds(analysis)
        lines.append("")
        if threshold.passed:
            lines.append("Threshold check: PASSED")
        else:
            lines.append("Threshold check: FAILED")
            for f in threshold.failures:
                lines.append(f"  - {f}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # JSON report
    # ------------------------------------------------------------------

    def report_json(self, analysis: AnalysisResult) -> str:
        """Generate a JSON coverage report."""
        threshold = self.check_thresholds(analysis)

        obj: dict[str, Any] = {
            "overall": {
                "line_rate": round(analysis.overall_line_rate, 4),
                "function_rate": round(analysis.overall_function_rate, 4),
                "branch_rate": round(analysis.overall_branch_rate, 4),
                "risk": analysis.overall_risk,
            },
            "threshold": {
                "passed": threshold.passed,
                "failures": list(threshold.failures),
            },
            "files": [
                {
                    "path": fa.path,
                    "line_rate": round(fa.line_rate, 4),
                    "function_rate": round(fa.function_rate, 4),
                    "branch_rate": round(fa.branch_rate, 4),
                    "risk": fa.risk,
                }
                for fa in analysis.file_assessments
            ],
            "uncovered_functions": [
                {
                    "file": uf.file_path,
                    "name": uf.name,
                    "start_line": uf.start_line,
                    "end_line": uf.end_line,
                    "risk": uf.risk,
                }
                for uf in analysis.uncovered_functions
            ],
            "gaps": [
                {
                    "file": g.file_path,
                    "start_line": g.start_line,
                    "end_line": g.end_line,
                    "line_count": g.line_count,
                    "risk": g.risk,
                }
                for g in analysis.gaps
            ],
        }
        return json.dumps(obj, indent=2)

    # ------------------------------------------------------------------
    # HTML report
    # ------------------------------------------------------------------

    def report_html(self, analysis: AnalysisResult) -> str:
        """Generate a simple HTML coverage report."""
        rows: list[str] = []
        for fa in analysis.file_assessments:
            rows.append(
                f"<tr><td>{fa.path}</td>"
                f"<td>{fa.line_rate:.0%}</td>"
                f"<td>{fa.function_rate:.0%}</td>"
                f"<td>{fa.branch_rate:.0%}</td>"
                f"<td>{fa.risk}</td></tr>"
            )

        table_rows = "\n".join(rows)
        return (
            "<!DOCTYPE html>\n<html>\n<head><title>Coverage Report</title></head>\n"
            "<body>\n"
            f"<h1>Coverage Report</h1>\n"
            f"<p>Line rate: {analysis.overall_line_rate:.1%} | "
            f"Function rate: {analysis.overall_function_rate:.1%} | "
            f"Branch rate: {analysis.overall_branch_rate:.1%} | "
            f"Risk: {analysis.overall_risk}</p>\n"
            "<table border='1'>\n"
            "<tr><th>File</th><th>Lines</th><th>Functions</th>"
            "<th>Branches</th><th>Risk</th></tr>\n"
            f"{table_rows}\n"
            "</table>\n"
            "</body>\n</html>"
        )

    # ------------------------------------------------------------------
    # Trend tracking
    # ------------------------------------------------------------------

    def build_trend(self, snapshots: Sequence[CoverageSnapshot]) -> TrendReport:
        """Build a trend report from a sequence of snapshots."""
        points: list[TrendPoint] = []
        for snap in snapshots:
            total_fns = snap.total_functions
            fn_rate = snap.covered_functions / total_fns if total_fns else 0.0
            total_br = snap.total_branches
            br_rate = snap.covered_branches / total_br if total_br else 0.0
            points.append(
                TrendPoint(
                    timestamp=snap.timestamp,
                    line_rate=snap.line_rate,
                    branch_rate=br_rate,
                    function_rate=fn_rate,
                    total_lines=snap.total_lines,
                )
            )
        return TrendReport(points=tuple(points))
