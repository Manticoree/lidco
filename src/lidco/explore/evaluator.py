"""Score and evaluate exploration variant results."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvaluationCriteria:
    tests_passed: bool = False
    lint_clean: bool = False
    diff_lines: int = 0
    complexity_delta: int = 0  # negative = reduced complexity
    token_cost: int = 0
    error_count: int = 0


@dataclass
class EvaluationWeights:
    tests: float = 0.35
    lint: float = 0.15
    diff_size: float = 0.20
    complexity: float = 0.15
    cost: float = 0.10
    errors: float = 0.05


@dataclass
class EvaluationResult:
    variant_id: str
    total_score: float
    breakdown: dict[str, float]
    rank: int = 0
    recommendation: str = ""


class ResultEvaluator:
    def __init__(self, weights: EvaluationWeights | None = None):
        self._weights = weights or EvaluationWeights()

    @property
    def weights(self) -> EvaluationWeights:
        return self._weights

    def evaluate(self, variant_id: str, criteria: EvaluationCriteria) -> EvaluationResult:
        """Evaluate a single variant."""
        breakdown: dict[str, float] = {}

        # Tests: binary
        breakdown["tests"] = self._weights.tests if criteria.tests_passed else 0.0

        # Lint: binary
        breakdown["lint"] = self._weights.lint if criteria.lint_clean else 0.0

        # Diff size: smaller is better, normalize to [0, weight]
        diff_score = max(0.0, 1.0 - criteria.diff_lines / 500.0)
        breakdown["diff_size"] = diff_score * self._weights.diff_size

        # Complexity: reduction is good
        if criteria.complexity_delta < 0:
            breakdown["complexity"] = self._weights.complexity
        elif criteria.complexity_delta == 0:
            breakdown["complexity"] = self._weights.complexity * 0.5
        else:
            breakdown["complexity"] = 0.0

        # Cost: lower is better
        cost_score = max(0.0, 1.0 - criteria.token_cost / 10000.0)
        breakdown["cost"] = cost_score * self._weights.cost

        # Errors: fewer is better
        error_score = 1.0 if criteria.error_count == 0 else max(0.0, 1.0 - criteria.error_count / 10.0)
        breakdown["errors"] = error_score * self._weights.errors

        total = sum(breakdown.values())

        return EvaluationResult(
            variant_id=variant_id,
            total_score=round(total, 4),
            breakdown=breakdown,
        )

    def rank_variants(self, evaluations: list[EvaluationResult]) -> list[EvaluationResult]:
        """Rank evaluations by total score (highest first). Returns new list."""
        sorted_evals = sorted(evaluations, key=lambda e: e.total_score, reverse=True)
        result = []
        for i, ev in enumerate(sorted_evals):
            if i == 0:
                recommendation = "Winner — best overall score"
            elif ev.total_score >= sorted_evals[0].total_score * 0.9:
                recommendation = "Strong alternative"
            else:
                recommendation = "Lower priority"
            result.append(EvaluationResult(
                variant_id=ev.variant_id,
                total_score=ev.total_score,
                breakdown=dict(ev.breakdown),
                rank=i + 1,
                recommendation=recommendation,
            ))
        return result

    def pick_winner(self, evaluations: list[EvaluationResult]) -> EvaluationResult | None:
        """Return the highest-scored evaluation, or None if empty."""
        if not evaluations:
            return None
        ranked = self.rank_variants(evaluations)
        return ranked[0]
