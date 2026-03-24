"""FlowEngine — decomposes goals into steps and executes them."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"
    PAUSED = "paused"


@dataclass
class FlowStep:
    index: int
    name: str
    description: str
    status: StepStatus = StepStatus.PENDING
    checkpoint_id: str | None = None
    error: str | None = None
    result: str | None = None


@dataclass
class Flow:
    goal: str
    steps: list[FlowStep]
    created_at: float = field(default_factory=time.time)


@dataclass
class FlowResult:
    flow: Flow
    success: bool
    completed_steps: int
    failed_step: FlowStep | None = None
    error: str | None = None


class FlowEngine:
    """Decomposes a goal into steps and executes them with checkpoints."""

    def __init__(self) -> None:
        self._current_flow: Flow | None = None
        self._paused = False
        self._step_executor: Callable[[FlowStep], str] | None = None
        self._pending_instructions: list[str] = []

    @property
    def current_flow(self) -> Flow | None:
        return self._current_flow

    @property
    def is_paused(self) -> bool:
        return self._paused

    def set_executor(self, fn: Callable[[FlowStep], str]) -> None:
        """Set the function that executes a single step."""
        self._step_executor = fn

    def plan(self, goal: str, steps: list[str] | None = None) -> Flow:
        """Create a Flow from a goal. If steps not provided, creates a single step."""
        if steps is None:
            step_list = [FlowStep(index=0, name="Execute", description=goal)]
        else:
            step_list = [
                FlowStep(index=i, name=s, description=s)
                for i, s in enumerate(steps)
            ]
        flow = Flow(goal=goal, steps=step_list)
        self._current_flow = flow
        return flow

    @property
    def pending_instructions(self) -> list[str]:
        return list(self._pending_instructions)

    def inject_instruction(self, instruction: str) -> bool:
        """Inject an instruction to be applied to remaining steps between executions."""
        if self._current_flow is None:
            return False
        self._pending_instructions.append(instruction)
        return True

    def _apply_pending_instructions(self, remaining_steps: list[FlowStep]) -> None:
        """Apply accumulated instructions to remaining step descriptions."""
        if not self._pending_instructions:
            return
        instruction_text = "; ".join(self._pending_instructions)
        for step in remaining_steps:
            if step.status == StepStatus.PENDING:
                step.description = f"{step.description} [Note: {instruction_text}]"
        self._pending_instructions.clear()

    def execute(self, flow: Flow) -> FlowResult:
        """Execute all steps in the flow sequentially."""
        self._paused = False
        completed = 0

        for step in flow.steps:
            self._apply_pending_instructions(flow.steps)

            if self._paused:
                step.status = StepStatus.PAUSED
                continue

            step.status = StepStatus.RUNNING
            try:
                if self._step_executor:
                    result = self._step_executor(step)
                    step.result = result
                else:
                    step.result = f"executed: {step.description}"
                step.status = StepStatus.DONE
                completed += 1
            except Exception as exc:
                step.status = StepStatus.FAILED
                step.error = str(exc)
                self._paused = True
                return FlowResult(
                    flow=flow,
                    success=False,
                    completed_steps=completed,
                    failed_step=step,
                    error=str(exc),
                )

        return FlowResult(
            flow=flow,
            success=True,
            completed_steps=completed,
        )

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def skip_step(self, step_index: int) -> bool:
        if self._current_flow is None:
            return False
        for step in self._current_flow.steps:
            if step.index == step_index and step.status == StepStatus.PAUSED:
                step.status = StepStatus.SKIPPED
                return True
        return False

    def status(self) -> dict:
        if self._current_flow is None:
            return {"active": False}
        steps = [
            {"index": s.index, "name": s.name, "status": s.status.value}
            for s in self._current_flow.steps
        ]
        return {
            "active": True,
            "goal": self._current_flow.goal,
            "paused": self._paused,
            "steps": steps,
        }
