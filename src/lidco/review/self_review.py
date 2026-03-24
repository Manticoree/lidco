"""SelfReviewer — agent reviews its own diff before PR submission."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class SelfReviewResult:
    issues: list[str]
    score: float  # 0-1; >= 0.8 means no revision needed
    needs_revision: bool
    suggestions: str
    iteration: int = 1


class SelfReviewer:
    """Spawn a review sub-agent to examine the agent's own diff."""

    MAX_ITERATIONS = 2

    def __init__(self, review_fn: Callable[[str, str], dict] | None = None) -> None:
        """
        review_fn(diff, context) -> {"issues": [...], "score": 0.0-1.0, "suggestions": "..."}
        """
        self._review_fn = review_fn

    def review(self, diff: str, context: str = "") -> SelfReviewResult:
        """Review a diff. Returns SelfReviewResult."""
        if not diff.strip():
            return SelfReviewResult(issues=[], score=1.0, needs_revision=False, suggestions="")

        if self._review_fn is None:
            return SelfReviewResult(issues=[], score=0.9, needs_revision=False, suggestions="")

        try:
            raw = self._review_fn(diff, context)
        except Exception:
            return SelfReviewResult(issues=[], score=0.5, needs_revision=False, suggestions="")

        issues = raw.get("issues", [])
        score = float(raw.get("score", 0.5))
        suggestions = raw.get("suggestions", "")
        needs_revision = score < 0.8

        return SelfReviewResult(
            issues=issues,
            score=score,
            needs_revision=needs_revision,
            suggestions=suggestions,
        )

    def review_with_iterations(self, diff: str, context: str = "", fix_fn: Callable[[str, str], str] | None = None) -> SelfReviewResult:
        """Review and optionally iterate up to MAX_ITERATIONS times."""
        current_diff = diff
        for iteration in range(1, self.MAX_ITERATIONS + 1):
            result = self.review(current_diff, context)
            result.iteration = iteration
            if not result.needs_revision or fix_fn is None:
                return result
            try:
                current_diff = fix_fn(current_diff, result.suggestions)
            except Exception:
                return result
        return result
