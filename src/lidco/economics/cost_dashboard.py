"""Cost Dashboard — aggregated cost breakdowns and session reports."""
from __future__ import annotations

from dataclasses import dataclass

from lidco.economics.cost_hook import CostRecord


@dataclass(frozen=True)
class CostBreakdown:
    """Per-model cost aggregation."""

    model: str
    count: int
    total_cost: float
    avg_cost: float


class CostDashboard:
    """Build cost breakdowns from CostRecord tuples.

    Immutable-style: :meth:`add_record` returns a *new* dashboard.
    """

    def __init__(self, records: tuple[CostRecord, ...] = ()) -> None:
        self._records = records

    def add_record(self, record: CostRecord) -> CostDashboard:
        """Return a new dashboard with *record* appended."""
        return CostDashboard((*self._records, record))

    def breakdown(self) -> tuple[CostBreakdown, ...]:
        """Per-model breakdown sorted by total cost descending."""
        agg: dict[str, list[float]] = {}
        for r in self._records:
            agg.setdefault(r.model, []).append(r.cost)
        items = []
        for model, costs in agg.items():
            total = sum(costs)
            items.append(
                CostBreakdown(
                    model=model,
                    count=len(costs),
                    total_cost=total,
                    avg_cost=total / len(costs) if costs else 0.0,
                )
            )
        items.sort(key=lambda b: b.total_cost, reverse=True)
        return tuple(items)

    @property
    def session_total(self) -> float:
        """Total cost across all records."""
        return sum(r.cost for r in self._records)

    def format_report(self) -> str:
        """Human-readable cost report."""
        if not self._records:
            return "No cost records."
        lines = [f"Session total: ${self.session_total:.6f}"]
        for b in self.breakdown():
            lines.append(
                f"  {b.model}: {b.count} calls, ${b.total_cost:.6f} "
                f"(avg ${b.avg_cost:.6f})"
            )
        return "\n".join(lines)


__all__ = ["CostBreakdown", "CostDashboard"]
