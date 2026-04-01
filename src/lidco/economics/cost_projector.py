"""Cost Projector — estimate remaining spend and detect anomalies."""
from __future__ import annotations

from dataclasses import dataclass

from lidco.economics.cost_hook import CostRecord


@dataclass(frozen=True)
class Projection:
    """Projected cost estimate."""

    estimated_total: float
    remaining: float
    confidence: float
    anomaly: bool


class CostProjector:
    """Projects future costs and detects anomalies based on history.

    Parameters
    ----------
    records:
        Historical cost records.
    """

    def __init__(self, records: tuple[CostRecord, ...] = ()) -> None:
        self._records = records

    def project(self, remaining_turns: int) -> Projection:
        """Estimate total cost including *remaining_turns* future calls."""
        if not self._records:
            return Projection(
                estimated_total=0.0,
                remaining=0.0,
                confidence=0.0,
                anomaly=False,
            )
        costs = [r.cost for r in self._records]
        avg = sum(costs) / len(costs)
        current_total = sum(costs)
        estimated_remaining = avg * remaining_turns
        estimated_total = current_total + estimated_remaining

        # Confidence decreases with fewer data points
        confidence = min(1.0, len(costs) / 10.0)

        return Projection(
            estimated_total=estimated_total,
            remaining=estimated_remaining,
            confidence=confidence,
            anomaly=False,
        )

    def detect_anomaly(self, latest: CostRecord) -> bool:
        """Return True if *latest* cost is anomalously high (>3x average)."""
        if not self._records:
            return False
        costs = [r.cost for r in self._records]
        avg = sum(costs) / len(costs)
        if avg <= 0:
            return latest.cost > 0
        return latest.cost > avg * 3.0

    def trend(self) -> str:
        """Return 'increasing', 'stable', or 'decreasing' based on recent costs."""
        if len(self._records) < 2:
            return "stable"
        costs = [r.cost for r in self._records]
        first_half = costs[: len(costs) // 2]
        second_half = costs[len(costs) // 2 :]
        avg_first = sum(first_half) / len(first_half) if first_half else 0
        avg_second = sum(second_half) / len(second_half) if second_half else 0
        if avg_second > avg_first * 1.1:
            return "increasing"
        if avg_second < avg_first * 0.9:
            return "decreasing"
        return "stable"


__all__ = ["Projection", "CostProjector"]
