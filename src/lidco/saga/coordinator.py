"""SagaCoordinator — compensating-transaction saga pattern (stdlib only)."""
from __future__ import annotations

import enum
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


class SagaStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    FAILED = "failed"


@dataclass
class SagaStep:
    """A single step in a saga with a forward action and compensating action."""
    name: str
    action: Callable[..., Any]
    compensation: Callable[..., None]
    description: str = ""


@dataclass
class SagaStepResult:
    step_name: str
    success: bool
    result: Any = None
    error: str = ""


@dataclass
class SagaResult:
    saga_id: str
    status: SagaStatus
    steps_completed: list[str] = field(default_factory=list)
    steps_compensated: list[str] = field(default_factory=list)
    error: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class SagaCoordinator:
    """
    Orchestrates a sequence of saga steps with automatic compensation on failure.

    Usage::

        coord = SagaCoordinator()
        coord.add_step("reserve", action=reserve_fn, compensation=release_fn)
        coord.add_step("charge", action=charge_fn, compensation=refund_fn)
        result = coord.execute(context={"order_id": "123"})
    """

    def __init__(self) -> None:
        self._steps: list[SagaStep] = []
        self._lock = threading.Lock()

    def add_step(
        self,
        name: str,
        action: Callable[..., Any],
        compensation: Callable[..., None],
        description: str = "",
    ) -> "SagaCoordinator":
        """Add a step.  Returns self for chaining."""
        step = SagaStep(
            name=name,
            action=action,
            compensation=compensation,
            description=description,
        )
        with self._lock:
            self._steps = [*self._steps, step]
        return self

    def execute(self, context: dict[str, Any] | None = None) -> SagaResult:
        """
        Execute all steps in order.

        If any step fails, compensate completed steps in reverse order.

        Parameters
        ----------
        context:
            Shared mutable dict passed to every action/compensation.
        """
        saga_id = str(uuid.uuid4())
        ctx = dict(context or {})
        completed: list[SagaStep] = []
        steps_completed: list[str] = []
        step_data: dict[str, Any] = {}

        with self._lock:
            steps = list(self._steps)

        status = SagaStatus.RUNNING

        for step in steps:
            try:
                result = step.action(ctx)
                completed.append(step)
                steps_completed.append(step.name)
                if result is not None:
                    step_data[step.name] = result
            except Exception as exc:
                # Compensate in reverse order
                status = SagaStatus.COMPENSATING
                compensated: list[str] = []
                for done_step in reversed(completed):
                    try:
                        done_step.compensation(ctx)
                        compensated.append(done_step.name)
                    except Exception:
                        pass  # best-effort compensation
                return SagaResult(
                    saga_id=saga_id,
                    status=SagaStatus.FAILED,
                    steps_completed=steps_completed,
                    steps_compensated=compensated,
                    error=f"Step {step.name!r} failed: {exc}",
                    data=step_data,
                )

        return SagaResult(
            saga_id=saga_id,
            status=SagaStatus.COMPLETED,
            steps_completed=steps_completed,
            data=step_data,
        )

    def step_count(self) -> int:
        with self._lock:
            return len(self._steps)

    def step_names(self) -> list[str]:
        with self._lock:
            return [s.name for s in self._steps]

    def clear(self) -> None:
        with self._lock:
            self._steps = []
