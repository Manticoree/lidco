"""EnsembleRunner — run N parallel agents, auto-select best result."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class CandidateResult:
    agent_id: str
    output: str
    score: float = 0.0
    test_passed: bool = False
    duration: float = 0.0


@dataclass
class EnsembleResult:
    candidates: list[CandidateResult]
    best: CandidateResult
    selection_reason: str


class EnsembleRunner:
    """Run N agents on the same task, select the best result."""

    def __init__(
        self,
        agent_fn: Callable[[str, str], str] | None = None,
        test_fn: Callable[[str], bool] | None = None,
        score_fn: Callable[[CandidateResult], float] | None = None,
    ) -> None:
        """
        agent_fn(agent_id, task) -> output
        test_fn(output) -> bool (did tests pass?)
        score_fn(candidate) -> float (quality score 0-1)
        """
        self._agent_fn = agent_fn
        self._test_fn = test_fn
        self._score_fn = score_fn

    def run(self, task: str, n: int = 3) -> EnsembleResult:
        """Run n agents on task and return best result."""
        candidates = []
        for i in range(n):
            agent_id = f"agent_{i}"
            t0 = time.time()
            try:
                output = self._agent_fn(agent_id, task) if self._agent_fn else f"result_{i}"
            except Exception as exc:
                output = f"error: {exc}"
            duration = time.time() - t0

            test_passed = self._test_fn(output) if self._test_fn else False
            candidate = CandidateResult(
                agent_id=agent_id,
                output=output,
                test_passed=test_passed,
                duration=duration,
            )
            candidate.score = self.score(candidate)
            candidates.append(candidate)

        best, reason = self._select_best(candidates)
        return EnsembleResult(candidates=candidates, best=best, selection_reason=reason)

    def score(self, candidate: CandidateResult) -> float:
        """Score a candidate. Custom score_fn overrides default heuristics."""
        if self._score_fn:
            return self._score_fn(candidate)
        # Default: test-passing bonus + prefer shorter output as tiebreak
        base = 0.8 if candidate.test_passed else 0.2
        length_penalty = min(len(candidate.output) / 10000, 0.1)
        return round(base - length_penalty, 4)

    def _select_best(self, candidates: list[CandidateResult]) -> tuple[CandidateResult, str]:
        if not candidates:
            raise ValueError("No candidates to select from")

        passing = [c for c in candidates if c.test_passed]
        if passing:
            best = max(passing, key=lambda c: c.score)
            return best, f"selected {best.agent_id}: tests passed, score={best.score:.2f}"

        best = max(candidates, key=lambda c: c.score)
        return best, f"selected {best.agent_id}: highest score={best.score:.2f} (no tests passed)"
