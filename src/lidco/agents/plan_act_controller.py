"""Plan/Act mode controller — separate planning from execution (Cline parity)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


Mode = str  # "plan" | "act"


@dataclass
class ActionStep:
    index: int
    description: str
    tool: str = ""          # tool to use: "browser", "file_edit", "bash", etc.
    args: dict[str, Any] = field(default_factory=dict)
    status: str = "pending" # "pending" | "done" | "failed" | "skipped"
    result: Any = None
    error: str = ""


@dataclass
class PlanActResult:
    mode: Mode
    steps: list[ActionStep]
    completed: int
    failed: int

    @property
    def success(self) -> bool:
        return self.failed == 0

    def format_summary(self) -> str:
        icons = {"pending": "○", "done": "✓", "failed": "✗", "skipped": "-"}
        lines = [f"[{self.mode.upper()} MODE] {self.completed}/{len(self.steps)} steps completed"]
        for s in self.steps:
            icon = icons.get(s.status, "?")
            lines.append(f"  {icon} {s.index}. {s.description}")
        return "\n".join(lines)


class PlanActController:
    """Implements Cline-style Plan/Act mode.

    PLAN mode: generate and display steps for user review.
    ACT mode: execute the approved plan step by step.
    """

    def __init__(
        self,
        executor: Callable[[ActionStep], Awaitable[Any]] | None = None,
        confirm_callback: Callable[[list[ActionStep]], Awaitable[bool]] | None = None,
    ) -> None:
        self._executor = executor
        self._confirm = confirm_callback
        self._mode: Mode = "plan"
        self._current_plan: list[ActionStep] = []

    @property
    def mode(self) -> Mode:
        return self._mode

    def set_mode(self, mode: Mode) -> None:
        if mode not in ("plan", "act"):
            raise ValueError(f"Invalid mode: {mode!r}")
        self._mode = mode

    def build_plan(self, steps: list[dict[str, Any]]) -> list[ActionStep]:
        """Create ActionStep list from dicts with 'description' key."""
        self._current_plan = [
            ActionStep(
                index=i + 1,
                description=s.get("description", f"Step {i+1}"),
                tool=s.get("tool", ""),
                args=s.get("args", {}),
            )
            for i, s in enumerate(steps)
        ]
        return self._current_plan

    def format_plan(self) -> str:
        if not self._current_plan:
            return "No plan loaded."
        lines = ["Proposed plan:"]
        for step in self._current_plan:
            tool_str = f" [{step.tool}]" if step.tool else ""
            lines.append(f"  {step.index}.{tool_str} {step.description}")
        return "\n".join(lines)

    async def execute_plan(
        self,
        steps: list[ActionStep] | None = None,
        *,
        auto_approve: bool = False,
    ) -> PlanActResult:
        """Execute plan in ACT mode.

        If confirm_callback is set and auto_approve is False, asks user first.
        """
        plan = steps if steps is not None else self._current_plan
        if not plan:
            return PlanActResult(mode="act", steps=[], completed=0, failed=0)

        if not auto_approve and self._confirm is not None:
            approved = await self._confirm(plan)
            if not approved:
                for s in plan:
                    s.status = "skipped"
                return PlanActResult(mode="act", steps=plan, completed=0, failed=0)

        completed = failed = 0
        for step in plan:
            if self._executor is None:
                step.status = "done"
                step.result = f"(no executor) {step.description}"
                completed += 1
                continue
            try:
                step.status = "done"
                step.result = await self._executor(step)
                completed += 1
            except Exception as e:
                step.status = "failed"
                step.error = str(e)
                failed += 1

        self._mode = "plan"  # reset to plan after execution
        return PlanActResult(mode="act", steps=plan, completed=completed, failed=failed)

    async def plan_then_act(
        self,
        raw_steps: list[dict[str, Any]],
        *,
        auto_approve: bool = False,
    ) -> PlanActResult:
        """Convenience: build plan → optionally confirm → execute."""
        self._mode = "plan"
        plan = self.build_plan(raw_steps)
        self._mode = "act"
        return await self.execute_plan(plan, auto_approve=auto_approve)
