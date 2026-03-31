"""Analyze coverage data to find untested code paths."""

from __future__ import annotations

from dataclasses import dataclass, field
import json


@dataclass
class CoverageGap:
    file_path: str
    line_numbers: list[int]
    gap_type: str  # "function", "branch", "block"
    name: str  # function/class name if identifiable
    risk_score: float  # 0.0-1.0, higher = more risky
    suggestion: str  # test suggestion text


@dataclass
class CoverageReport:
    total_statements: int
    covered_statements: int
    coverage_percent: float
    gaps: list[CoverageGap]
    files_analyzed: int


class CoverageGapAnalyzer:
    def __init__(self, min_risk: float = 0.3):
        self._min_risk = min_risk

    @property
    def min_risk(self) -> float:
        return self._min_risk

    def analyze_coverage_json(self, coverage_data: dict) -> CoverageReport:
        """Analyze coverage.py JSON report format."""
        gaps: list[CoverageGap] = []
        total_stmts = 0
        covered_stmts = 0
        files_analyzed = 0

        files = coverage_data.get("files", {})
        for file_path, file_data in files.items():
            files_analyzed += 1
            summary = file_data.get("summary", {})
            total_stmts += summary.get("num_statements", 0)
            covered_stmts += summary.get("covered_lines", 0)

            missing_lines = file_data.get("missing_lines", [])
            if not missing_lines:
                continue

            # Group consecutive missing lines into gaps
            line_groups = self._group_consecutive(missing_lines)
            for group in line_groups:
                risk = self._calculate_risk(
                    len(group), summary.get("num_statements", 1)
                )
                if risk >= self._min_risk:
                    gaps.append(
                        CoverageGap(
                            file_path=file_path,
                            line_numbers=group,
                            gap_type="block",
                            name=(
                                f"lines {group[0]}-{group[-1]}"
                                if len(group) > 1
                                else f"line {group[0]}"
                            ),
                            risk_score=risk,
                            suggestion=f"Add test covering {file_path}:{group[0]}-{group[-1]}",
                        )
                    )

        pct = (covered_stmts / total_stmts * 100) if total_stmts > 0 else 0.0
        # Sort gaps by risk score descending
        gaps.sort(key=lambda g: g.risk_score, reverse=True)

        return CoverageReport(
            total_statements=total_stmts,
            covered_statements=covered_stmts,
            coverage_percent=pct,
            gaps=gaps,
            files_analyzed=files_analyzed,
        )

    def analyze_from_file(self, json_path: str) -> CoverageReport:
        """Load and analyze coverage JSON from file path."""
        with open(json_path, "r") as f:
            data = json.load(f)
        return self.analyze_coverage_json(data)

    def get_top_gaps(self, report: CoverageReport, n: int = 10) -> list[CoverageGap]:
        """Return top N gaps by risk score."""
        return report.gaps[:n]

    def format_report(self, report: CoverageReport) -> str:
        """Format coverage gap report as readable text."""
        lines = [
            f"Coverage: {report.coverage_percent:.1f}% "
            f"({report.covered_statements}/{report.total_statements} statements)",
            f"Files analyzed: {report.files_analyzed}",
            f"Gaps found: {len(report.gaps)}",
            "",
        ]
        for i, gap in enumerate(report.gaps[:10], 1):
            lines.append(
                f"  {i}. [{gap.risk_score:.2f}] {gap.file_path} "
                f"— {gap.name} ({gap.gap_type})"
            )
            lines.append(f"     {gap.suggestion}")
        return "\n".join(lines)

    def _group_consecutive(self, numbers: list[int]) -> list[list[int]]:
        """Group consecutive integers into sublists."""
        if not numbers:
            return []
        sorted_nums = sorted(numbers)
        groups: list[list[int]] = [[sorted_nums[0]]]
        for n in sorted_nums[1:]:
            if n == groups[-1][-1] + 1:
                groups[-1].append(n)
            else:
                groups.append([n])
        return groups

    def _calculate_risk(self, gap_size: int, total_statements: int) -> float:
        """Calculate risk score for a coverage gap. Larger gaps = higher risk."""
        if total_statements == 0:
            return 0.0
        size_factor = min(gap_size / 10.0, 1.0)  # Normalize: 10+ lines = max
        proportion = gap_size / total_statements
        return min(size_factor * 0.6 + proportion * 0.4, 1.0)
