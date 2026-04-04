"""GoalValidator — validate goal completion against acceptance criteria."""
from __future__ import annotations

from dataclasses import dataclass, field

from lidco.goals.parser import Goal


@dataclass
class ValidationResult:
    """Outcome of validating a goal against results."""

    passed: bool
    criteria_met: list[str] = field(default_factory=list)
    criteria_failed: list[str] = field(default_factory=list)


class GoalValidator:
    """Validate whether goal acceptance criteria are satisfied."""

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def validate(self, goal: Goal, results: dict[str, bool]) -> ValidationResult:
        """Check each acceptance criterion against *results*.

        *results* maps criterion text (or substring) to ``True``/``False``.
        Criteria not found in *results* are considered failed.
        """
        met: list[str] = []
        failed: list[str] = []

        for criterion in goal.acceptance_criteria:
            if self._criterion_satisfied(criterion, results):
                met.append(criterion)
            else:
                failed.append(criterion)

        return ValidationResult(
            passed=len(failed) == 0 and len(met) > 0,
            criteria_met=met,
            criteria_failed=failed,
        )

    def validate_partial(
        self, goal: Goal, results: dict[str, bool], threshold: float = 0.5,
    ) -> ValidationResult:
        """Validate with a pass threshold (fraction of criteria that must pass)."""
        full = self.validate(goal, results)
        total = len(full.criteria_met) + len(full.criteria_failed)
        if total == 0:
            return ValidationResult(passed=False, criteria_met=[], criteria_failed=[])
        ratio = len(full.criteria_met) / total
        return ValidationResult(
            passed=ratio >= threshold,
            criteria_met=full.criteria_met,
            criteria_failed=full.criteria_failed,
        )

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    @staticmethod
    def _criterion_satisfied(criterion: str, results: dict[str, bool]) -> bool:
        """Check if *criterion* is satisfied by any key in *results*."""
        # Exact match first
        if criterion in results:
            return bool(results[criterion])
        # Substring match
        lower_crit = criterion.lower()
        for key, val in results.items():
            if lower_crit in key.lower() or key.lower() in lower_crit:
                return bool(val)
        return False
