"""Pareto-optimal model selection based on cost and quality."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelProfile:
    """Cost/quality/latency profile for a model."""

    model: str
    avg_quality: float
    avg_cost_per_token: float
    avg_latency_ms: float


class CostQualityOptimizer:
    """Find Pareto-optimal model configurations."""

    def __init__(self) -> None:
        self._profiles: list[ModelProfile] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_profile(self, profile: ModelProfile) -> None:
        self._profiles = [*self._profiles, profile]

    def optimize(
        self,
        min_quality: float = 0.0,
        max_cost: float | None = None,
    ) -> list[ModelProfile]:
        """Return Pareto-optimal profiles (quality desc) within constraints."""
        candidates = [
            p
            for p in self._profiles
            if p.avg_quality >= min_quality
            and (max_cost is None or p.avg_cost_per_token <= max_cost)
        ]
        front = self._pareto(candidates)
        return sorted(front, key=lambda p: p.avg_quality, reverse=True)

    def recommend(
        self,
        min_quality: float = 0.5,
        max_cost: float | None = None,
    ) -> ModelProfile | None:
        """Best quality model within budget."""
        optimal = self.optimize(min_quality=min_quality, max_cost=max_cost)
        return optimal[0] if optimal else None

    def pareto_front(self) -> list[ModelProfile]:
        """All profiles on the Pareto frontier (no constraints)."""
        return self._pareto(list(self._profiles))

    @property
    def profiles(self) -> list[ModelProfile]:
        return list(self._profiles)

    def summary(self) -> dict:
        """Overview statistics."""
        if not self._profiles:
            return {"count": 0, "pareto_size": 0, "profiles": []}
        front = self.pareto_front()
        return {
            "count": len(self._profiles),
            "pareto_size": len(front),
            "profiles": [
                {
                    "model": p.model,
                    "quality": round(p.avg_quality, 4),
                    "cost": round(p.avg_cost_per_token, 6),
                    "latency": round(p.avg_latency_ms, 1),
                }
                for p in self._profiles
            ],
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _pareto(profiles: list[ModelProfile]) -> list[ModelProfile]:
        """Return non-dominated profiles (higher quality, lower cost is better)."""
        front: list[ModelProfile] = []
        for candidate in profiles:
            dominated = False
            for other in profiles:
                if other is candidate:
                    continue
                # other dominates candidate if it is at least as good on both
                # axes and strictly better on at least one
                if (
                    other.avg_quality >= candidate.avg_quality
                    and other.avg_cost_per_token <= candidate.avg_cost_per_token
                    and (
                        other.avg_quality > candidate.avg_quality
                        or other.avg_cost_per_token < candidate.avg_cost_per_token
                    )
                ):
                    dominated = True
                    break
            if not dominated:
                front.append(candidate)
        return front
