"""Composite codebase health score."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class HealthDimension:
    """A single scored dimension of project health."""

    name: str
    score: float
    weight: float = 1.0
    detail: str = ""


@dataclass(frozen=True)
class HealthReport:
    """Aggregated health report."""

    overall_score: float
    dimensions: tuple[HealthDimension, ...] = ()
    timestamp: float = 0.0
    project_path: str = ""


class HealthScorer:
    """Compute a weighted composite health score from multiple dimensions."""

    def __init__(self) -> None:
        self._dimensions: list[HealthDimension] = []
        self._project_path: str = ""

    # -- mutation ----------------------------------------------------------

    def add_dimension(
        self,
        name: str,
        score: float,
        weight: float = 1.0,
        detail: str = "",
    ) -> None:
        clamped = max(0.0, min(100.0, float(score)))
        self._dimensions.append(
            HealthDimension(name=name, score=clamped, weight=weight, detail=detail)
        )

    def set_project(self, path: str) -> None:
        self._project_path = path

    def reset(self) -> None:
        self._dimensions = []
        self._project_path = ""

    # -- computation -------------------------------------------------------

    def compute(self) -> HealthReport:
        if not self._dimensions:
            return HealthReport(
                overall_score=0.0,
                dimensions=(),
                timestamp=time.time(),
                project_path=self._project_path,
            )

        total_weight = sum(d.weight for d in self._dimensions)
        if total_weight == 0:
            weighted = 0.0
        else:
            weighted = sum(d.score * d.weight for d in self._dimensions) / total_weight

        return HealthReport(
            overall_score=round(weighted, 2),
            dimensions=tuple(self._dimensions),
            timestamp=time.time(),
            project_path=self._project_path,
        )

    def grade(self) -> str:
        report = self.compute()
        score = report.overall_score
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"

    @staticmethod
    def trend(reports: list[HealthReport]) -> str:
        if len(reports) < 2:
            return "stable"
        first = reports[0].overall_score
        last = reports[-1].overall_score
        delta = last - first
        if delta > 2:
            return "improving"
        if delta < -2:
            return "declining"
        return "stable"
