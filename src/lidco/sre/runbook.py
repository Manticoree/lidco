"""Runbook Generator — generate runbooks from procedures, decision trees, automated checks, versioning.

Stdlib only.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class RunbookError(Exception):
    """Raised when a runbook operation fails."""


class StepType(str, Enum):
    MANUAL = "manual"
    AUTOMATED = "automated"
    DECISION = "decision"
    CHECK = "check"


@dataclass
class RunbookStep:
    """A single step in a runbook."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = ""
    description: str = ""
    step_type: StepType = StepType.MANUAL
    command: str = ""
    expected_output: str = ""
    on_success: str = ""  # step id to go to
    on_failure: str = ""  # step id to go to
    timeout_seconds: float = 300.0
    tags: list[str] = field(default_factory=list)


@dataclass
class DecisionNode:
    """A decision point in a runbook decision tree."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    question: str = ""
    yes_step: str = ""  # step or node id
    no_step: str = ""   # step or node id


@dataclass
class CheckResult:
    """Result of running an automated check step."""

    step_id: str
    passed: bool
    output: str = ""
    duration_seconds: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class Runbook:
    """A versioned operational runbook."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    steps: list[RunbookStep] = field(default_factory=list)
    decisions: list[DecisionNode] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)
    author: str = ""

    def step_count(self) -> int:
        return len(self.steps)

    def automated_steps(self) -> list[RunbookStep]:
        return [s for s in self.steps if s.step_type in (StepType.AUTOMATED, StepType.CHECK)]

    def render_markdown(self) -> str:
        lines = [
            f"# {self.name}",
            "",
            f"**Version:** {self.version}",
            f"**Author:** {self.author}" if self.author else "",
            f"**Description:** {self.description}" if self.description else "",
            "",
            "## Steps",
            "",
        ]
        for i, step in enumerate(self.steps, 1):
            kind = f"[{step.step_type.value}]"
            lines.append(f"{i}. {kind} **{step.title}**")
            if step.description:
                lines.append(f"   {step.description}")
            if step.command:
                lines.append(f"   ```\n   {step.command}\n   ```")
            lines.append("")
        if self.decisions:
            lines.append("## Decision Tree")
            lines.append("")
            for d in self.decisions:
                lines.append(f"- **{d.question}**")
                lines.append(f"  - Yes → {d.yes_step}")
                lines.append(f"  - No → {d.no_step}")
            lines.append("")
        return "\n".join(lines)


class RunbookGenerator:
    """Generate, manage, and version runbooks."""

    def __init__(self) -> None:
        self._runbooks: dict[str, Runbook] = {}
        self._check_handlers: dict[str, Callable[[], CheckResult]] = {}

    # ---- CRUD ----

    def create(self, name: str, description: str = "", author: str = "", version: str = "1.0.0") -> Runbook:
        if not name:
            raise RunbookError("Runbook name is required")
        rb = Runbook(name=name, description=description, author=author, version=version)
        self._runbooks[rb.id] = rb
        return rb

    def get(self, runbook_id: str) -> Runbook:
        if runbook_id not in self._runbooks:
            raise RunbookError(f"Runbook not found: {runbook_id}")
        return self._runbooks[runbook_id]

    def list_runbooks(self) -> list[Runbook]:
        return list(self._runbooks.values())

    def remove(self, runbook_id: str) -> None:
        if runbook_id not in self._runbooks:
            raise RunbookError(f"Runbook not found: {runbook_id}")
        del self._runbooks[runbook_id]

    # ---- Steps ----

    def add_step(self, runbook_id: str, step: RunbookStep) -> RunbookStep:
        rb = self.get(runbook_id)
        rb.steps.append(step)
        rb.updated_at = time.time()
        return step

    def add_decision(self, runbook_id: str, decision: DecisionNode) -> DecisionNode:
        rb = self.get(runbook_id)
        rb.decisions.append(decision)
        rb.updated_at = time.time()
        return decision

    # ---- Automated checks ----

    def register_check(self, step_id: str, handler: Callable[[], CheckResult]) -> None:
        self._check_handlers[step_id] = handler

    def run_check(self, step_id: str) -> CheckResult:
        if step_id not in self._check_handlers:
            raise RunbookError(f"No check handler for step: {step_id}")
        start = time.time()
        result = self._check_handlers[step_id]()
        result.duration_seconds = time.time() - start
        return result

    def run_all_checks(self, runbook_id: str) -> list[CheckResult]:
        rb = self.get(runbook_id)
        results: list[CheckResult] = []
        for step in rb.automated_steps():
            if step.id in self._check_handlers:
                results.append(self.run_check(step.id))
        return results

    # ---- Versioning ----

    def new_version(self, runbook_id: str, new_version: str) -> Runbook:
        """Create a new version of a runbook (copy)."""
        original = self.get(runbook_id)
        new_rb = Runbook(
            name=original.name,
            description=original.description,
            version=new_version,
            steps=list(original.steps),
            decisions=list(original.decisions),
            tags=list(original.tags),
            author=original.author,
        )
        self._runbooks[new_rb.id] = new_rb
        return new_rb

    # ---- Generation helpers ----

    def from_procedure(self, name: str, procedure_lines: list[str], author: str = "") -> Runbook:
        """Generate a runbook from a list of procedure description lines."""
        rb = self.create(name=name, author=author)
        for i, line in enumerate(procedure_lines):
            stripped = line.strip()
            if not stripped:
                continue
            step_type = StepType.MANUAL
            if stripped.startswith("[auto]") or stripped.startswith("[automated]"):
                step_type = StepType.AUTOMATED
                stripped = stripped.split("]", 1)[1].strip()
            elif stripped.startswith("[check]"):
                step_type = StepType.CHECK
                stripped = stripped.split("]", 1)[1].strip()
            elif stripped.startswith("[decision]"):
                step_type = StepType.DECISION
                stripped = stripped.split("]", 1)[1].strip()
            step = RunbookStep(title=stripped, step_type=step_type)
            self.add_step(rb.id, step)
        return rb
