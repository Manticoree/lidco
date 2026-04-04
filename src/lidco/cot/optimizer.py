"""CoTOptimizer — optimize reasoning chains by removing redundancy."""
from __future__ import annotations

from dataclasses import dataclass, field

from lidco.cot.planner import ReasoningStep, StepStatus


@dataclass
class OptimizationResult:
    """Result of chain optimization."""

    original_steps: int
    optimized_steps: int
    removed_steps: list[str] = field(default_factory=list)
    parallelizable_groups: list[list[str]] = field(default_factory=list)
    estimated_savings_tokens: int = 0


class CoTOptimizer:
    """Optimize reasoning chains — remove redundancy, parallelize, cache."""

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}  # description -> cached result

    def find_redundant(self, steps: list[ReasoningStep]) -> list[str]:
        """Find steps with duplicate or very similar descriptions."""
        seen: dict[str, str] = {}
        redundant: list[str] = []
        for step in steps:
            key = step.description.lower().strip()
            if key in seen:
                redundant.append(step.step_id)
            else:
                seen[key] = step.step_id
        return redundant

    def find_parallelizable(self, steps: list[ReasoningStep]) -> list[list[str]]:
        """Find groups of steps that can run in parallel (no mutual deps)."""
        # Group by dependency level
        levels: dict[int, list[str]] = {}
        step_level: dict[str, int] = {}

        for step in steps:
            if not step.depends_on:
                level = 0
            else:
                level = max(step_level.get(d, 0) for d in step.depends_on) + 1
            step_level[step.step_id] = level
            levels.setdefault(level, []).append(step.step_id)

        # Groups with >1 step can be parallelized
        return [ids for ids in levels.values() if len(ids) > 1]

    def optimize(self, steps: list[ReasoningStep]) -> OptimizationResult:
        """Full optimization pass."""
        redundant = self.find_redundant(steps)
        parallel = self.find_parallelizable(steps)

        # Remove redundant steps
        optimized = [s for s in steps if s.step_id not in redundant]
        savings = sum(s.estimated_tokens for s in steps if s.step_id in redundant)

        return OptimizationResult(
            original_steps=len(steps),
            optimized_steps=len(optimized),
            removed_steps=redundant,
            parallelizable_groups=parallel,
            estimated_savings_tokens=savings,
        )

    def cache_result(self, description: str, result: str) -> None:
        """Cache a step result for reuse."""
        self._cache[description.lower().strip()] = result

    def get_cached(self, description: str) -> str | None:
        """Get cached result for a step description."""
        return self._cache.get(description.lower().strip())

    def cache_size(self) -> int:
        return len(self._cache)

    def clear_cache(self) -> None:
        self._cache.clear()
