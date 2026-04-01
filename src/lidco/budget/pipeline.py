"""Ordered budget pipeline -- estimate -> check -> execute -> record -> compact."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PipelineStage(str, Enum):
    """Stages of the budget pipeline."""

    ESTIMATE = "estimate"
    CHECK = "check"
    EXECUTE = "execute"
    RECORD = "record"
    COMPACT = "compact"


@dataclass(frozen=True)
class PipelineResult:
    """Immutable result from a single pipeline stage."""

    stage: PipelineStage
    passed: bool = True
    message: str = ""
    tokens: int = 0


class BudgetPipeline:
    """Ordered pipeline: estimate -> check -> execute -> record -> compact."""

    def __init__(self, budget_limit: int = 128_000) -> None:
        self._budget_limit = budget_limit
        self._budget_remaining = budget_limit
        self._stages: list[PipelineResult] = []
        self._results: list[PipelineResult] = []
        self._last_check_passed = True

    def estimate(self, tool_name: str, args: str = "") -> PipelineResult:
        """Estimate cost using len(args)//4 heuristic."""
        estimated = max(len(args) // 4, 1)
        result = PipelineResult(
            stage=PipelineStage.ESTIMATE,
            passed=True,
            message=f"Estimated {estimated} tokens for {tool_name}",
            tokens=estimated,
        )
        self._results = [*self._results, result]
        return result

    def check(self, estimated_tokens: int) -> PipelineResult:
        """Check if estimated tokens fit within remaining budget."""
        passed = estimated_tokens <= self._budget_remaining
        result = PipelineResult(
            stage=PipelineStage.CHECK,
            passed=passed,
            message="Within budget" if passed else f"Over budget by {estimated_tokens - self._budget_remaining}",
            tokens=estimated_tokens,
        )
        self._last_check_passed = passed
        self._results = [*self._results, result]
        return result

    def execute_gate(self) -> PipelineResult:
        """Return pass/fail based on last check."""
        result = PipelineResult(
            stage=PipelineStage.EXECUTE,
            passed=self._last_check_passed,
            message="Execution approved" if self._last_check_passed else "Execution blocked",
        )
        self._results = [*self._results, result]
        return result

    def record(self, actual_tokens: int) -> PipelineResult:
        """Subtract actual tokens from budget and record."""
        self._budget_remaining = max(0, self._budget_remaining - actual_tokens)
        result = PipelineResult(
            stage=PipelineStage.RECORD,
            passed=True,
            message=f"Recorded {actual_tokens} tokens, {self._budget_remaining} remaining",
            tokens=actual_tokens,
        )
        self._results = [*self._results, result]
        return result

    def compact_check(self, utilization: float) -> PipelineResult:
        """Recommend compaction if utilization > 0.85."""
        needs_compact = utilization > 0.85
        result = PipelineResult(
            stage=PipelineStage.COMPACT,
            passed=not needs_compact,
            message="Compaction recommended" if needs_compact else "No compaction needed",
        )
        self._results = [*self._results, result]
        return result

    def run(
        self, tool_name: str, args: str = "", actual_tokens: int = 0,
    ) -> list[PipelineResult]:
        """Run all stages in order and return list of results."""
        results: list[PipelineResult] = []

        est = self.estimate(tool_name, args)
        results.append(est)

        chk = self.check(est.tokens)
        results.append(chk)

        gate = self.execute_gate()
        results.append(gate)

        if gate.passed:
            tokens_to_record = actual_tokens if actual_tokens > 0 else est.tokens
            rec = self.record(tokens_to_record)
            results.append(rec)

        used = self._budget_limit - self._budget_remaining
        util = used / self._budget_limit if self._budget_limit > 0 else 0.0
        cmp = self.compact_check(util)
        results.append(cmp)

        return results

    def remaining(self) -> int:
        """Tokens remaining in budget."""
        return self._budget_remaining

    def summary(self) -> str:
        """Human-readable pipeline summary."""
        used = self._budget_limit - self._budget_remaining
        util = used / self._budget_limit * 100 if self._budget_limit > 0 else 0.0
        return (
            f"Pipeline: {used:,}/{self._budget_limit:,} used ({util:.1f}%), "
            f"{len(self._results)} stages run"
        )
