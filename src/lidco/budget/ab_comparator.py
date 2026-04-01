"""Compare budget efficiency between sessions or models."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ComparisonResult:
    """Immutable result of an A/B budget comparison."""

    label_a: str
    label_b: str
    tokens_a: int = 0
    tokens_b: int = 0
    efficiency_a: float = 0.0
    efficiency_b: float = 0.0
    cost_a: float = 0.0
    cost_b: float = 0.0
    winner: str = ""
    savings: float = 0.0


def _pick_winner(
    label_a: str,
    eff_a: float,
    cost_a: float,
    label_b: str,
    eff_b: float,
    cost_b: float,
) -> str:
    """Determine winner: higher efficiency wins unless costs differ greatly."""
    cost_ratio = abs(cost_a - cost_b) / max(cost_a, cost_b, 0.0001)
    eff_ratio = abs(eff_a - eff_b) / max(eff_a, eff_b, 0.0001)

    # If costs differ by >20% and efficiencies are close, cheaper wins
    if cost_ratio > 0.2 and eff_ratio < 0.1:
        return label_a if cost_a < cost_b else label_b
    # Otherwise higher efficiency wins
    if eff_a > eff_b:
        return label_a
    if eff_b > eff_a:
        return label_b
    # Tie: cheaper wins
    return label_a if cost_a <= cost_b else label_b


class ABComparator:
    """Compare budget efficiency between two sessions or models."""

    def __init__(self) -> None:
        self._comparisons: list[ComparisonResult] = []

    def compare(
        self,
        label_a: str,
        tokens_a: int,
        efficiency_a: float,
        cost_a: float,
        label_b: str,
        tokens_b: int,
        efficiency_b: float,
        cost_b: float,
    ) -> ComparisonResult:
        """Compare two budget profiles and determine winner."""
        winner = _pick_winner(label_a, efficiency_a, cost_a, label_b, efficiency_b, cost_b)
        savings = abs(cost_a - cost_b)
        result = ComparisonResult(
            label_a=label_a,
            label_b=label_b,
            tokens_a=tokens_a,
            tokens_b=tokens_b,
            efficiency_a=efficiency_a,
            efficiency_b=efficiency_b,
            cost_a=cost_a,
            cost_b=cost_b,
            winner=winner,
            savings=round(savings, 6),
        )
        self._comparisons = [*self._comparisons, result]
        return result

    def compare_models(
        self,
        model_a: str,
        stats_a: dict,
        model_b: str,
        stats_b: dict,
    ) -> ComparisonResult:
        """Compare two models using stats dicts with tokens/efficiency/cost keys."""
        return self.compare(
            label_a=model_a,
            tokens_a=stats_a.get("tokens", 0),
            efficiency_a=stats_a.get("efficiency", 0.0),
            cost_a=stats_a.get("cost", 0.0),
            label_b=model_b,
            tokens_b=stats_b.get("tokens", 0),
            efficiency_b=stats_b.get("efficiency", 0.0),
            cost_b=stats_b.get("cost", 0.0),
        )

    def get_comparisons(self) -> list[ComparisonResult]:
        """Return all recorded comparisons."""
        return list(self._comparisons)

    def best_of(self, comparisons: list[ComparisonResult]) -> str:
        """Return the most frequent winner across comparisons."""
        if not comparisons:
            return ""
        counts: Counter[str] = Counter(c.winner for c in comparisons)
        return counts.most_common(1)[0][0]

    def summary(self, result: ComparisonResult) -> str:
        """Human-readable summary of a comparison."""
        return (
            f"{result.label_a} vs {result.label_b}: "
            f"efficiency {result.efficiency_a:.2f} vs {result.efficiency_b:.2f}, "
            f"cost ${result.cost_a:.4f} vs ${result.cost_b:.4f} — "
            f"winner: {result.winner} (savings: ${result.savings:.4f})"
        )
