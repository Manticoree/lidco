"""Interactive plan validation — show plan to user, allow edits before execution."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class PlanStep:
    index: int
    description: str
    status: str = "pending"   # pending | approved | skipped | done | failed


@dataclass
class ValidationResult:
    approved: bool
    steps: list[PlanStep]
    user_notes: str = ""

    @property
    def approved_steps(self) -> list[PlanStep]:
        return [s for s in self.steps if s.status not in ("skipped",)]


class PlanValidator:
    """Parse, display, and validate a multi-step plan before execution.

    Supports both interactive (TTY) and programmatic approval.
    """

    def __init__(
        self,
        confirm_callback: Callable[[str], Awaitable[bool]] | None = None,
    ) -> None:
        """
        Args:
            confirm_callback: async fn(plan_text) -> bool. If None, auto-approves.
        """
        self._confirm = confirm_callback

    def parse_steps(self, plan_text: str) -> list[PlanStep]:
        """Extract numbered steps from plan text."""
        steps: list[PlanStep] = []
        for line in plan_text.splitlines():
            stripped = line.strip()
            # Match: "1. Do something" or "1) Do something"
            for sep in (". ", ") "):
                if sep in stripped:
                    prefix, rest = stripped.split(sep, 1)
                    if prefix.isdigit():
                        idx = int(prefix)
                        steps.append(PlanStep(index=idx, description=rest.strip()))
                        break
        return steps

    def format_plan(self, steps: list[PlanStep]) -> str:
        """Format steps for display."""
        lines = ["Plan:"]
        for step in steps:
            icon = {"pending": "○", "approved": "✓", "skipped": "✗", "done": "●", "failed": "✗"}.get(step.status, "○")
            lines.append(f"  {icon} {step.index}. {step.description}")
        return "\n".join(lines)

    async def validate(self, plan_text: str, auto_approve: bool = False) -> ValidationResult:
        """Present plan to user and collect approval.

        Args:
            plan_text: Raw plan text (may contain numbered steps).
            auto_approve: Skip interactive confirmation.
        """
        steps = self.parse_steps(plan_text)
        if not steps:
            # No numbered steps — wrap entire plan as step 1
            steps = [PlanStep(index=1, description=plan_text.strip())]

        if auto_approve or self._confirm is None:
            for s in steps:
                s.status = "approved"
            return ValidationResult(approved=True, steps=steps)

        approved = await self._confirm(self.format_plan(steps))
        for s in steps:
            s.status = "approved" if approved else "skipped"
        return ValidationResult(approved=approved, steps=steps, user_notes="")

    def apply_edits(self, steps: list[PlanStep], edits: dict[int, str]) -> list[PlanStep]:
        """Apply user edits to step descriptions.

        Args:
            edits: {step_index: new_description}
        """
        result: list[PlanStep] = []
        for step in steps:
            if step.index in edits:
                result.append(PlanStep(index=step.index, description=edits[step.index], status=step.status))
            else:
                result.append(step)
        return result

    def skip_steps(self, steps: list[PlanStep], indices: list[int]) -> list[PlanStep]:
        """Mark specific steps as skipped."""
        return [
            PlanStep(index=s.index, description=s.description, status="skipped" if s.index in indices else s.status)
            for s in steps
        ]
