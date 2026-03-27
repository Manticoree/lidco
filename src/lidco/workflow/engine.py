"""Workflow Engine — define and execute multi-step automation workflows (stdlib only).

Inspired by GitHub Actions / n8n: workflows are ordered sequences of steps
where each step can have conditions, inputs from previous outputs, and
simple loops.  All execution is synchronous and stdlib-only.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class WorkflowError(Exception):
    """Raised when a workflow definition or execution fails."""


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class StepResult:
    """Result of executing a single workflow step."""

    name: str
    status: StepStatus
    output: Any = None
    error: str = ""
    duration_ms: float = 0.0

    @property
    def success(self) -> bool:
        return self.status == StepStatus.SUCCESS

    @property
    def skipped(self) -> bool:
        return self.status == StepStatus.SKIPPED


@dataclass
class WorkflowResult:
    """Aggregate result of running an entire workflow."""

    workflow_name: str
    steps: list[StepResult] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    finished_at: float = 0.0

    @property
    def success(self) -> bool:
        return all(s.success or s.skipped for s in self.steps)

    @property
    def failed_steps(self) -> list[StepResult]:
        return [s for s in self.steps if s.status == StepStatus.FAILED]

    @property
    def duration_ms(self) -> float:
        return (self.finished_at - self.started_at) * 1000

    def summary(self) -> str:
        total = len(self.steps)
        ok = sum(1 for s in self.steps if s.success)
        skipped = sum(1 for s in self.steps if s.skipped)
        failed = len(self.failed_steps)
        status = "OK" if self.success else "FAILED"
        return (
            f"Workflow '{self.workflow_name}' [{status}] "
            f"{ok}/{total} ok, {skipped} skipped, {failed} failed "
            f"({self.duration_ms:.0f}ms)"
        )


# Step action type: receives context dict, returns output value
StepAction = Callable[[dict[str, Any]], Any]
ConditionFn = Callable[[dict[str, Any]], bool]


@dataclass
class WorkflowStep:
    """A single unit of work in a workflow."""

    name: str
    action: StepAction
    condition: ConditionFn | None = None   # skip step when False
    inputs: dict[str, str] = field(default_factory=dict)   # key → context_key
    output_key: str = ""                   # store output at this context key
    on_error: str = "fail"                 # "fail" | "skip" | "continue"

    def should_run(self, ctx: dict[str, Any]) -> bool:
        if self.condition is None:
            return True
        return bool(self.condition(ctx))

    def resolve_inputs(self, ctx: dict[str, Any]) -> dict[str, Any]:
        """Build a kwargs dict from context using inputs mapping."""
        return {k: ctx.get(v) for k, v in self.inputs.items()}


class WorkflowEngine:
    """Defines and runs named multi-step workflows.

    Usage::

        engine = WorkflowEngine()

        @engine.step("greet", output_key="msg")
        def greet(ctx):
            return f"Hello, {ctx.get('name', 'world')}!"

        @engine.step("shout", inputs={"text": "msg"})
        def shout(ctx, text=None):
            return (text or "").upper()

        result = engine.run("my_workflow", initial_context={"name": "Alice"})
        print(result.summary())

    Steps registered via ``engine.step()`` are appended to the default
    workflow list.  For named workflows, use ``define()`` + ``run()``.
    """

    def __init__(self) -> None:
        self._workflows: dict[str, list[WorkflowStep]] = {}
        self._default: list[WorkflowStep] = []

    # ------------------------------------------------------------------ #
    # Definition API                                                        #
    # ------------------------------------------------------------------ #

    def define(self, name: str, steps: list[WorkflowStep]) -> None:
        """Register a named workflow."""
        if not name.strip():
            raise WorkflowError("Workflow name must not be empty")
        self._workflows[name] = list(steps)

    def step(
        self,
        name: str,
        *,
        condition: ConditionFn | None = None,
        inputs: dict[str, str] | None = None,
        output_key: str = "",
        on_error: str = "fail",
    ) -> Callable[[StepAction], StepAction]:
        """Decorator: register a step and append it to the default workflow."""
        def decorator(fn: StepAction) -> StepAction:
            ws = WorkflowStep(
                name=name,
                action=fn,
                condition=condition,
                inputs=inputs or {},
                output_key=output_key,
                on_error=on_error,
            )
            self._default.append(ws)
            return fn
        return decorator

    def add_step(self, workflow_name: str, step: WorkflowStep) -> None:
        self._workflows.setdefault(workflow_name, []).append(step)

    def list_workflows(self) -> list[str]:
        names = list(self._workflows.keys())
        if self._default:
            names.append("__default__")
        return names

    # ------------------------------------------------------------------ #
    # Execution                                                             #
    # ------------------------------------------------------------------ #

    def run(
        self,
        workflow_name: str = "__default__",
        initial_context: dict[str, Any] | None = None,
        stop_on_first_failure: bool = True,
    ) -> WorkflowResult:
        """Execute a workflow and return its result."""
        if workflow_name == "__default__":
            steps = self._default
        elif workflow_name in self._workflows:
            steps = self._workflows[workflow_name]
        else:
            raise WorkflowError(f"Unknown workflow: {workflow_name!r}")

        ctx: dict[str, Any] = dict(initial_context or {})
        result = WorkflowResult(workflow_name=workflow_name, context=ctx)

        for wf_step in steps:
            step_result = self._execute_step(wf_step, ctx)
            result.steps.append(step_result)

            if step_result.status == StepStatus.FAILED and stop_on_first_failure:
                break

        result.finished_at = time.time()
        return result

    def _execute_step(
        self, wf_step: WorkflowStep, ctx: dict[str, Any]
    ) -> StepResult:
        if not wf_step.should_run(ctx):
            return StepResult(name=wf_step.name, status=StepStatus.SKIPPED)

        t0 = time.time()
        try:
            kwargs = wf_step.resolve_inputs(ctx)
            output = wf_step.action(ctx, **kwargs)
            if wf_step.output_key:
                ctx[wf_step.output_key] = output
            duration = (time.time() - t0) * 1000
            return StepResult(
                name=wf_step.name,
                status=StepStatus.SUCCESS,
                output=output,
                duration_ms=duration,
            )
        except Exception as exc:  # noqa: BLE001
            duration = (time.time() - t0) * 1000
            on_error = wf_step.on_error
            if on_error == "skip":
                status = StepStatus.SKIPPED
            elif on_error == "continue":
                status = StepStatus.SUCCESS
            else:
                status = StepStatus.FAILED
            return StepResult(
                name=wf_step.name,
                status=status,
                error=str(exc),
                duration_ms=duration,
            )
