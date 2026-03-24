"""ConfidenceEstimator — score agent action confidence to decide when to ask."""
from __future__ import annotations

from dataclasses import dataclass, field

_ACTION_RISK: dict[str, float] = {
    "file_delete": 0.3,
    "bash": 0.5,
    "file_write": 0.6,
    "file_edit": 0.65,
    "git_push": 0.4,
    "git_reset": 0.35,
    "file_read": 0.9,
    "glob": 0.95,
    "grep": 0.95,
    "web_search": 0.85,
}
_DEFAULT_RISK = 0.7
_DEFAULT_THRESHOLD = 0.7


@dataclass
class ConfidenceScore:
    value: float
    factors: dict[str, float]
    should_ask: bool

    @property
    def is_confident(self) -> bool:
        return not self.should_ask


class ConfidenceEstimator:
    """Score each agent action on a 0–1 confidence scale."""

    def __init__(self, threshold: float = _DEFAULT_THRESHOLD) -> None:
        self._threshold = threshold

    @property
    def threshold(self) -> float:
        return self._threshold

    @threshold.setter
    def threshold(self, value: float) -> None:
        self._threshold = max(0.0, min(1.0, value))

    def score(
        self,
        action_type: str,
        params: dict,
        context: str = "",
    ) -> ConfidenceScore:
        """Compute a ConfidenceScore for an action."""
        task_clarity = _score_task_clarity(context)
        context_completeness = _score_context_completeness(params, context)
        action_risk = _ACTION_RISK.get(action_type, _DEFAULT_RISK)
        conflict_detected = _detect_conflict(context)

        factors = {
            "task_clarity": task_clarity,
            "context_completeness": context_completeness,
            "action_risk": action_risk,
            "conflict_detected": 0.0 if conflict_detected else 1.0,
        }

        value = (
            task_clarity * 0.3
            + context_completeness * 0.2
            + action_risk * 0.4
            + factors["conflict_detected"] * 0.1
        )
        value = max(0.0, min(1.0, value))

        return ConfidenceScore(
            value=value,
            factors=factors,
            should_ask=value < self._threshold,
        )


def _score_task_clarity(context: str) -> float:
    """Higher if context is specific and detailed."""
    if not context:
        return 0.3
    words = len(context.split())
    if words < 3:
        return 0.4
    if words < 10:
        return 0.65
    return 0.85


def _score_context_completeness(params: dict, context: str) -> float:
    """Higher when params are fully specified."""
    if not params:
        return 0.5
    filled = sum(1 for v in params.values() if v)
    ratio = filled / len(params)
    return 0.4 + ratio * 0.6


def _detect_conflict(context: str) -> bool:
    """True if conflicting instructions detected."""
    conflict_pairs = [
        ("delete", "keep"),
        ("remove", "preserve"),
        ("overwrite", "backup"),
    ]
    lower = context.lower()
    return any(a in lower and b in lower for a, b in conflict_pairs)
