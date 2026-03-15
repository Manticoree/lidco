"""Plan rollback on failure — Task 319.

Maintains a stack of plan checkpoints. When a plan step fails, the executor
can roll back to the last known-good checkpoint and retry from there.

Usage::

    tracker = PlanRollbackTracker()
    tracker.checkpoint("step 1 complete", state={"files_changed": ["auth.py"]})
    tracker.checkpoint("step 2 complete", state={"files_changed": ["auth.py", "tests/test_auth.py"]})

    # Step 3 fails — roll back to step 2
    cp = tracker.rollback()
    print(cp.label, cp.state)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlanCheckpoint:
    """A snapshot of plan execution state at a given point."""

    step_index: int
    label: str
    state: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    plan_snapshot: str = ""   # text of the plan at this checkpoint


class RollbackError(Exception):
    """Raised when rollback is not possible."""


class PlanRollbackTracker:
    """Tracks plan execution checkpoints and supports rollback.

    Args:
        max_checkpoints: Maximum checkpoints to retain (oldest are discarded).
    """

    def __init__(self, max_checkpoints: int = 20) -> None:
        self._checkpoints: list[PlanCheckpoint] = []
        self._max = max_checkpoints
        self._current_step: int = 0

    # ------------------------------------------------------------------
    # Checkpoint management
    # ------------------------------------------------------------------

    def checkpoint(
        self,
        label: str,
        state: dict[str, Any] | None = None,
        plan_snapshot: str = "",
    ) -> PlanCheckpoint:
        """Save a checkpoint at the current step.

        Args:
            label: Human-readable description (e.g. "Step 2 complete").
            state: Arbitrary state dict to restore on rollback.
            plan_snapshot: Serialised plan text at this point.
        """
        cp = PlanCheckpoint(
            step_index=self._current_step,
            label=label,
            state=dict(state or {}),
            plan_snapshot=plan_snapshot,
        )
        self._checkpoints.append(cp)
        if len(self._checkpoints) > self._max:
            self._checkpoints.pop(0)
        self._current_step += 1
        return cp

    def rollback(self, steps: int = 1) -> PlanCheckpoint:
        """Roll back *steps* checkpoints. Returns the restored checkpoint.

        Raises:
            RollbackError: If there are not enough checkpoints.
        """
        if not self._checkpoints:
            raise RollbackError("No checkpoints available to roll back to.")
        if steps > len(self._checkpoints):
            raise RollbackError(
                f"Cannot roll back {steps} steps — only {len(self._checkpoints)} checkpoint(s) available."
            )
        # Remove the last *steps* checkpoints and return the landing point
        for _ in range(steps):
            self._checkpoints.pop()
        cp = self._checkpoints[-1] if self._checkpoints else PlanCheckpoint(step_index=0, label="initial")
        self._current_step = cp.step_index
        return cp

    def rollback_to(self, label: str) -> PlanCheckpoint:
        """Roll back to the most recent checkpoint with *label*.

        Raises:
            RollbackError: If no checkpoint with that label exists.
        """
        for i in range(len(self._checkpoints) - 1, -1, -1):
            if self._checkpoints[i].label == label:
                to_remove = len(self._checkpoints) - 1 - i
                for _ in range(to_remove):
                    self._checkpoints.pop()
                cp = self._checkpoints[-1]
                self._current_step = cp.step_index
                return cp
        raise RollbackError(f"No checkpoint with label '{label}' found.")

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def current_checkpoint(self) -> PlanCheckpoint | None:
        """Return the most recent checkpoint, or None."""
        return self._checkpoints[-1] if self._checkpoints else None

    def list_checkpoints(self) -> list[PlanCheckpoint]:
        """Return all checkpoints in order."""
        return list(self._checkpoints)

    def count(self) -> int:
        return len(self._checkpoints)

    def clear(self) -> None:
        self._checkpoints.clear()
        self._current_step = 0

    @property
    def current_step(self) -> int:
        return self._current_step
