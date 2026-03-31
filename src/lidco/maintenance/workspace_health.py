"""Q148: Workspace health scoring."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Tuple


@dataclass
class HealthMetric:
    name: str
    score: float  # 0.0 – 1.0
    weight: float
    message: str


@dataclass
class HealthReport:
    overall_score: float
    metrics: list[HealthMetric] = field(default_factory=list)
    grade: str = "F"
    recommendations: list[str] = field(default_factory=list)


class WorkspaceHealth:
    """Evaluate workspace health via pluggable metric checks."""

    def __init__(self) -> None:
        self._checks: list[tuple[str, Callable[[], tuple[float, str]], float]] = []

    def add_metric(
        self,
        name: str,
        check_fn: Callable[[], tuple[float, str]],
        weight: float = 1.0,
    ) -> None:
        """Register a named health check."""
        self._checks.append((name, check_fn, weight))

    @staticmethod
    def grade(score: float) -> str:
        """Map a 0-1 score to a letter grade."""
        if score >= 0.9:
            return "A"
        if score >= 0.8:
            return "B"
        if score >= 0.7:
            return "C"
        if score >= 0.6:
            return "D"
        return "F"

    def evaluate(self) -> HealthReport:
        """Run all registered checks and produce a :class:`HealthReport`."""
        metrics: list[HealthMetric] = []
        total_weight = 0.0
        weighted_sum = 0.0
        recommendations: list[str] = []
        for name, fn, weight in self._checks:
            try:
                score, msg = fn()
            except Exception as exc:
                score = 0.0
                msg = f"Check failed: {exc}"
            score = max(0.0, min(1.0, score))
            metrics.append(HealthMetric(name=name, score=score, weight=weight, message=msg))
            weighted_sum += score * weight
            total_weight += weight
            if score < 0.7:
                recommendations.append(f"Improve '{name}': {msg}")
        overall = weighted_sum / total_weight if total_weight > 0 else 0.0
        return HealthReport(
            overall_score=round(overall, 4),
            metrics=metrics,
            grade=self.grade(overall),
            recommendations=recommendations,
        )

    @staticmethod
    def format_report(report: HealthReport) -> str:
        """Return a human-readable string for *report*."""
        lines = [
            f"Workspace Health: {report.grade} ({report.overall_score:.0%})",
            "",
        ]
        for m in report.metrics:
            bar = "#" * int(m.score * 10)
            lines.append(f"  {m.name:.<30s} {m.score:.0%} [{bar:<10s}] {m.message}")
        if report.recommendations:
            lines.append("")
            lines.append("Recommendations:")
            for r in report.recommendations:
                lines.append(f"  - {r}")
        return "\n".join(lines)
