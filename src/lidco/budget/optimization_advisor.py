"""Recommend budget optimizations based on usage patterns."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Priority(str, Enum):
    """Recommendation priority levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class Recommendation:
    """An immutable optimization recommendation."""

    action: str
    priority: Priority = Priority.MEDIUM
    estimated_savings: int = 0
    description: str = ""


class OptimizationAdvisor:
    """Analyze token usage and generate optimization recommendations."""

    def __init__(self) -> None:
        self._recommendations: list[Recommendation] = []

    def analyze(
        self,
        total_tokens: int,
        context_limit: int,
        compactions: int,
        tool_usage: dict[str, int] | None = None,
        turns: int = 0,
    ) -> list[Recommendation]:
        """Generate recommendations based on usage metrics."""
        recs: list[Recommendation] = []
        utilization = total_tokens / context_limit if context_limit > 0 else 0.0
        tool_usage = tool_usage or {}

        # HIGH: auto-compaction if none and utilization > 70%
        if compactions == 0 and utilization > 0.7:
            recs.append(
                Recommendation(
                    action="Enable auto-compaction",
                    priority=Priority.HIGH,
                    estimated_savings=int(total_tokens * 0.3),
                    description=(
                        "No compactions detected at "
                        f"{utilization:.0%} utilization. "
                        "Enable auto-compaction to reclaim tokens."
                    ),
                )
            )

        # HIGH: reduce tool result size if any tool > 30% of budget
        for name, tokens in tool_usage.items():
            if total_tokens > 0 and tokens / total_tokens > 0.3:
                recs.append(
                    Recommendation(
                        action="Reduce tool result size",
                        priority=Priority.HIGH,
                        estimated_savings=tokens // 2,
                        description=(
                            f"Tool '{name}' uses {tokens} tokens "
                            f"({tokens * 100 // total_tokens}% of budget). "
                            "Compress or truncate results."
                        ),
                    )
                )

        # MEDIUM: cheaper model if underutilized (<30%)
        if utilization < 0.3 and total_tokens > 0:
            recs.append(
                Recommendation(
                    action="Use cheaper model",
                    priority=Priority.MEDIUM,
                    estimated_savings=int(total_tokens * 0.4),
                    description=(
                        f"Only {utilization:.0%} of context used. "
                        "A smaller, cheaper model may suffice."
                    ),
                )
            )

        # MEDIUM: increase compaction frequency if utilization > 85%
        if utilization > 0.85 and compactions > 0:
            recs.append(
                Recommendation(
                    action="Increase compaction frequency",
                    priority=Priority.MEDIUM,
                    estimated_savings=int(total_tokens * 0.15),
                    description=(
                        f"Context at {utilization:.0%}. "
                        "More frequent compaction can prevent overflow."
                    ),
                )
            )

        # LOW: batch tool calls if many turns
        if turns > 20:
            recs.append(
                Recommendation(
                    action="Consider batch tool calls",
                    priority=Priority.LOW,
                    estimated_savings=turns * 50,
                    description=(
                        f"{turns} turns detected. "
                        "Batching tool calls reduces per-turn overhead."
                    ),
                )
            )

        self._recommendations = [*self._recommendations, *recs]
        return recs

    def get_recommendations(self) -> list[Recommendation]:
        """Return all accumulated recommendations."""
        return list(self._recommendations)

    def top(self, limit: int = 3) -> list[Recommendation]:
        """Return top recommendations by priority (HIGH first)."""
        order = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
        ranked = sorted(self._recommendations, key=lambda r: order.get(r.priority, 9))
        return ranked[:limit]

    def total_potential_savings(self) -> int:
        """Sum of estimated savings across all recommendations."""
        return sum(r.estimated_savings for r in self._recommendations)

    def summary(self) -> str:
        """Human-readable summary of recommendations."""
        n = len(self._recommendations)
        if n == 0:
            return "No optimization recommendations."
        savings = self.total_potential_savings()
        top = self.top(3)
        lines = [f"{n} recommendations (est. savings: {savings} tokens):"]
        for r in top:
            lines.append(f"  [{r.priority.value.upper()}] {r.action}: {r.description}")
        return "\n".join(lines)
