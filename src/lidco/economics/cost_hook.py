"""Cost Hook — real-time per-call cost tracking with model pricing lookup."""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    """Pricing definition for one model."""

    model: str
    input_cost_per_1k: float
    output_cost_per_1k: float


@dataclass(frozen=True)
class CostRecord:
    """Single cost record for one LLM call."""

    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    timestamp: str


class CostHook:
    """Tracks per-call costs using a pricing table.

    Parameters
    ----------
    pricing:
        Tuple of ModelPricing entries.  Unknown models are priced at 0.
    """

    def __init__(self, pricing: tuple[ModelPricing, ...] = ()) -> None:
        self._pricing: dict[str, ModelPricing] = {p.model: p for p in pricing}
        self._records: list[CostRecord] = []

    def record(self, model: str, input_tokens: int, output_tokens: int) -> CostRecord:
        """Record a single LLM call and return its CostRecord."""
        p = self._pricing.get(model)
        if p is not None:
            cost = (input_tokens / 1000.0) * p.input_cost_per_1k + (
                output_tokens / 1000.0
            ) * p.output_cost_per_1k
        else:
            cost = 0.0
        rec = CostRecord(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        self._records.append(rec)
        return rec

    @property
    def total_cost(self) -> float:
        """Sum of all recorded costs."""
        return sum(r.cost for r in self._records)

    @property
    def records(self) -> tuple[CostRecord, ...]:
        """All recorded cost entries (immutable copy)."""
        return tuple(self._records)

    def by_model(self) -> dict[str, float]:
        """Aggregate total cost per model."""
        result: dict[str, float] = {}
        for r in self._records:
            result[r.model] = result.get(r.model, 0.0) + r.cost
        return result


__all__ = ["ModelPricing", "CostRecord", "CostHook"]
