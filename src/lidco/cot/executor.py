"""StepExecutor — execute reasoning steps with checkpointing."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from lidco.cot.planner import ReasoningStep, StepStatus


@dataclass
class StepCheckpoint:
    """Checkpoint for a step execution."""

    step_id: str
    timestamp: float = field(default_factory=time.time)
    intermediate_result: str = ""
    tokens_used: int = 0


class StepExecutor:
    """Execute reasoning steps and manage checkpoints."""

    def __init__(self) -> None:
        self._checkpoints: list[StepCheckpoint] = []
        self._results: dict[str, str] = {}
        self._execution_log: list[dict] = []

    def execute(self, step: ReasoningStep, result: str) -> ReasoningStep:
        """Execute a step by recording its result."""
        step.status = StepStatus.IN_PROGRESS
        self._execution_log.append({
            "step_id": step.step_id,
            "action": "start",
            "timestamp": time.time(),
        })

        # Record checkpoint
        cp = StepCheckpoint(
            step_id=step.step_id,
            intermediate_result=result,
        )
        self._checkpoints.append(cp)

        step.result = result
        step.status = StepStatus.COMPLETED
        self._results[step.step_id] = result

        self._execution_log.append({
            "step_id": step.step_id,
            "action": "complete",
            "timestamp": time.time(),
        })
        return step

    def fail(self, step: ReasoningStep, reason: str) -> ReasoningStep:
        """Mark a step as failed."""
        step.status = StepStatus.FAILED
        step.result = f"FAILED: {reason}"
        self._execution_log.append({
            "step_id": step.step_id,
            "action": "fail",
            "reason": reason,
            "timestamp": time.time(),
        })
        return step

    def skip(self, step: ReasoningStep, reason: str = "") -> ReasoningStep:
        """Skip a step."""
        step.status = StepStatus.SKIPPED
        step.result = f"SKIPPED: {reason}" if reason else "SKIPPED"
        return step

    def get_result(self, step_id: str) -> str | None:
        return self._results.get(step_id)

    def checkpoints(self) -> list[StepCheckpoint]:
        return list(self._checkpoints)

    def checkpoint_for(self, step_id: str) -> StepCheckpoint | None:
        for cp in reversed(self._checkpoints):
            if cp.step_id == step_id:
                return cp
        return None

    def resume_from(self, step_id: str) -> StepCheckpoint | None:
        """Find checkpoint to resume from after failure."""
        return self.checkpoint_for(step_id)

    def execution_log(self) -> list[dict]:
        return list(self._execution_log)

    def summary(self) -> dict:
        return {
            "executed": len(self._results),
            "checkpoints": len(self._checkpoints),
            "log_entries": len(self._execution_log),
        }
