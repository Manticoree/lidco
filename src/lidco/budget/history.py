"""Historical budget data storage and querying."""
from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass(frozen=True)
class BudgetSnapshot:
    """Immutable record of budget state at a point in time."""

    session_id: str
    timestamp: float = field(default_factory=time.time)
    model: str = ""
    total_tokens: int = 0
    context_limit: int = 128000
    turns: int = 0
    compactions: int = 0
    efficiency: float = 0.0
    cost: float = 0.0


class BudgetHistory:
    """Store and query historical budget snapshots."""

    def __init__(self, max_entries: int = 1000) -> None:
        self._snapshots: list[BudgetSnapshot] = []
        self._max = max_entries

    def record(
        self,
        session_id: str,
        model: str = "",
        total_tokens: int = 0,
        context_limit: int = 128000,
        turns: int = 0,
        compactions: int = 0,
        efficiency: float = 0.0,
        cost: float = 0.0,
    ) -> BudgetSnapshot:
        """Record a new budget snapshot and return it."""
        snap = BudgetSnapshot(
            session_id=session_id,
            model=model,
            total_tokens=total_tokens,
            context_limit=context_limit,
            turns=turns,
            compactions=compactions,
            efficiency=efficiency,
            cost=cost,
        )
        self._snapshots = [*self._snapshots, snap]
        if len(self._snapshots) > self._max:
            self._snapshots = self._snapshots[-self._max :]
        return snap

    def query(
        self,
        model: str | None = None,
        min_efficiency: float = 0.0,
        limit: int = 50,
    ) -> list[BudgetSnapshot]:
        """Return snapshots matching filters, newest first."""
        results = [
            s
            for s in self._snapshots
            if (model is None or s.model == model) and s.efficiency >= min_efficiency
        ]
        return list(reversed(results))[:limit]

    def get_by_session(self, session_id: str) -> BudgetSnapshot | None:
        """Return the latest snapshot for a session, or None."""
        for snap in reversed(self._snapshots):
            if snap.session_id == session_id:
                return snap
        return None

    def average_efficiency(self, model: str | None = None) -> float:
        """Average efficiency across all (or model-filtered) snapshots."""
        filtered = [
            s for s in self._snapshots if model is None or s.model == model
        ]
        if not filtered:
            return 0.0
        return sum(s.efficiency for s in filtered) / len(filtered)

    def total_cost(self, model: str | None = None) -> float:
        """Sum of costs across all (or model-filtered) snapshots."""
        return sum(
            s.cost
            for s in self._snapshots
            if model is None or s.model == model
        )

    def trend(self, last_n: int = 10) -> list[BudgetSnapshot]:
        """Return the last N snapshots in chronological order."""
        return list(self._snapshots[-last_n:])

    def clear(self) -> None:
        """Remove all snapshots."""
        self._snapshots = []

    def export(self) -> list[dict]:
        """Export all snapshots as list of dicts."""
        return [
            {
                "session_id": s.session_id,
                "timestamp": s.timestamp,
                "model": s.model,
                "total_tokens": s.total_tokens,
                "context_limit": s.context_limit,
                "turns": s.turns,
                "compactions": s.compactions,
                "efficiency": s.efficiency,
                "cost": s.cost,
            }
            for s in self._snapshots
        ]

    def summary(self) -> str:
        """Return a human-readable summary."""
        n = len(self._snapshots)
        if n == 0:
            return "No budget history recorded."
        avg_eff = self.average_efficiency()
        total = self.total_cost()
        return (
            f"Budget history: {n} snapshots, "
            f"avg efficiency {avg_eff:.2f}, "
            f"total cost ${total:.4f}"
        )
