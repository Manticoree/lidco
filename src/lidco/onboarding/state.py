"""Onboarding progress state tracking — task 1105."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class StepStatus(Enum):
    """Status of an onboarding step."""

    PENDING = "pending"
    DONE = "done"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class OnboardingStep:
    """A single step in the onboarding flow."""

    name: str
    status: StepStatus
    completed_at: str | None


class OnboardingState:
    """Immutable onboarding progress tracker."""

    def __init__(self, steps: tuple[OnboardingStep, ...] = ()) -> None:
        self._steps = steps

    @property
    def steps(self) -> tuple[OnboardingStep, ...]:
        return self._steps

    def mark_done(self, name: str) -> "OnboardingState":
        """Return a new state with *name* marked DONE."""
        now = datetime.now(timezone.utc).isoformat()
        new_steps: list[OnboardingStep] = []
        found = False
        for step in self._steps:
            if step.name == name:
                new_steps.append(
                    OnboardingStep(name=step.name, status=StepStatus.DONE, completed_at=now)
                )
                found = True
            else:
                new_steps.append(step)
        if not found:
            new_steps.append(
                OnboardingStep(name=name, status=StepStatus.DONE, completed_at=now)
            )
        return OnboardingState(tuple(new_steps))

    def mark_skipped(self, name: str) -> "OnboardingState":
        """Return a new state with *name* marked SKIPPED."""
        now = datetime.now(timezone.utc).isoformat()
        new_steps: list[OnboardingStep] = []
        found = False
        for step in self._steps:
            if step.name == name:
                new_steps.append(
                    OnboardingStep(name=step.name, status=StepStatus.SKIPPED, completed_at=now)
                )
                found = True
            else:
                new_steps.append(step)
        if not found:
            new_steps.append(
                OnboardingStep(name=name, status=StepStatus.SKIPPED, completed_at=now)
            )
        return OnboardingState(tuple(new_steps))

    @property
    def is_complete(self) -> bool:
        """True when no steps are PENDING."""
        if not self._steps:
            return True
        return all(s.status != StepStatus.PENDING for s in self._steps)

    def pending(self) -> tuple[str, ...]:
        """Return names of PENDING steps."""
        return tuple(s.name for s in self._steps if s.status == StepStatus.PENDING)

    def progress(self) -> float:
        """Return completion ratio 0.0–1.0."""
        if not self._steps:
            return 1.0
        done_or_skipped = sum(
            1 for s in self._steps if s.status in (StepStatus.DONE, StepStatus.SKIPPED)
        )
        return done_or_skipped / len(self._steps)
