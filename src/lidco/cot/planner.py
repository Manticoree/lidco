"""CoTPlanner — plan reasoning steps for complex questions."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class StepStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ReasoningStep:
    """A single reasoning step."""

    step_id: str
    description: str
    depends_on: list[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: str | None = None
    estimated_tokens: int = 100


class CoTPlanner:
    """Plan and manage chains of reasoning steps."""

    def __init__(self) -> None:
        self._steps: dict[str, ReasoningStep] = {}
        self._order: list[str] = []
        self._counter = 0

    def add_step(
        self,
        description: str,
        depends_on: list[str] | None = None,
        estimated_tokens: int = 100,
    ) -> ReasoningStep:
        """Add a reasoning step."""
        self._counter += 1
        step_id = f"step-{self._counter}"
        step = ReasoningStep(
            step_id=step_id,
            description=description,
            depends_on=depends_on or [],
            estimated_tokens=estimated_tokens,
        )
        self._steps[step_id] = step
        self._order.append(step_id)
        return step

    def decompose(self, question: str, max_steps: int = 10) -> list[ReasoningStep]:
        """Decompose a complex question into reasoning steps."""
        # Heuristic decomposition based on complexity indicators
        parts = []
        sentences = [s.strip() for s in question.replace("?", "?.").split(".") if s.strip()]

        if len(sentences) <= 1:
            parts = ["Understand the question", "Analyze key concepts", "Formulate answer"]
        else:
            parts.append("Parse the multi-part question")
            for i, s in enumerate(sentences[:max_steps - 2]):
                parts.append(f"Address: {s[:80]}")
            parts.append("Synthesize final answer")

        steps = []
        prev_id = None
        for desc in parts[:max_steps]:
            deps = [prev_id] if prev_id else []
            step = self.add_step(desc, depends_on=deps)
            prev_id = step.step_id
            steps.append(step)
        return steps

    def get_step(self, step_id: str) -> ReasoningStep | None:
        return self._steps.get(step_id)

    def steps(self) -> list[ReasoningStep]:
        return [self._steps[sid] for sid in self._order if sid in self._steps]

    def ready_steps(self) -> list[ReasoningStep]:
        """Steps whose dependencies are all completed."""
        ready = []
        for step in self.steps():
            if step.status != StepStatus.PENDING:
                continue
            deps_met = all(
                self._steps.get(d, ReasoningStep(step_id="", description="")).status == StepStatus.COMPLETED
                for d in step.depends_on
            )
            if deps_met:
                ready.append(step)
        return ready

    def total_estimated_tokens(self) -> int:
        return sum(s.estimated_tokens for s in self._steps.values())

    def completion_pct(self) -> float:
        if not self._steps:
            return 0.0
        completed = sum(1 for s in self._steps.values() if s.status == StepStatus.COMPLETED)
        return round(completed / len(self._steps) * 100, 1)

    def dependency_order(self) -> list[str]:
        """Topological sort of step IDs."""
        visited: set[str] = set()
        result: list[str] = []

        def visit(sid: str) -> None:
            if sid in visited:
                return
            visited.add(sid)
            step = self._steps.get(sid)
            if step:
                for dep in step.depends_on:
                    visit(dep)
            result.append(sid)

        for sid in self._order:
            visit(sid)
        return result

    def summary(self) -> dict:
        return {
            "total_steps": len(self._steps),
            "completed": sum(1 for s in self._steps.values() if s.status == StepStatus.COMPLETED),
            "pending": sum(1 for s in self._steps.values() if s.status == StepStatus.PENDING),
            "failed": sum(1 for s in self._steps.values() if s.status == StepStatus.FAILED),
            "estimated_tokens": self.total_estimated_tokens(),
            "completion_pct": self.completion_pct(),
        }
