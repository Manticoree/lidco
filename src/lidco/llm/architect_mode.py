"""ArchitectMode — dual-model plan-then-execute session."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class FileChangeSpec:
    file: str
    action: str  # "create" | "modify" | "delete"
    description: str


@dataclass
class ArchitectPlan:
    rationale: str
    file_changes: list[FileChangeSpec]


@dataclass
class EditResult:
    file: str
    success: bool
    content: str = ""
    error: str = ""


class ArchitectSession:
    """Use architect_fn to plan and editor_fn to execute file changes."""

    def __init__(
        self,
        architect_fn: Callable[[str], str],
        editor_fn: Callable[[str, str], str] | None = None,
    ) -> None:
        self._architect_fn = architect_fn
        self._editor_fn = editor_fn

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    def plan(self, task: str) -> ArchitectPlan:
        """Call architect_fn with task; parse JSON into ArchitectPlan."""
        raw = self._architect_fn(task)
        return self._parse_plan(task, raw)

    def _parse_plan(self, task: str, raw: str) -> ArchitectPlan:
        """Parse JSON plan or fall back to a single-change plan."""
        raw = raw.strip()
        # Try to extract JSON block
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            try:
                data = json.loads(raw[start:end])
                changes = [
                    FileChangeSpec(
                        file=c.get("file", "unknown"),
                        action=c.get("action", "modify"),
                        description=c.get("description", ""),
                    )
                    for c in data.get("file_changes", [])
                ]
                return ArchitectPlan(
                    rationale=data.get("rationale", ""),
                    file_changes=changes,
                )
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

        # Fallback: treat the whole response as a single-file task
        return ArchitectPlan(
            rationale=raw,
            file_changes=[
                FileChangeSpec(file="<unknown>", action="modify", description=raw)
            ],
        )

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, plan: ArchitectPlan) -> list[EditResult]:
        """Call editor_fn per FileChangeSpec; return one EditResult per file."""
        results: list[EditResult] = []
        for spec in plan.file_changes:
            if self._editor_fn is None:
                results.append(EditResult(
                    file=spec.file,
                    success=True,
                    content=f"[stub: {spec.description}]",
                ))
                continue
            try:
                content = self._editor_fn(spec.file, spec.description)
                results.append(EditResult(file=spec.file, success=True, content=content))
            except Exception as exc:
                results.append(EditResult(file=spec.file, success=False, error=str(exc)))
        return results

    # ------------------------------------------------------------------
    # Combined
    # ------------------------------------------------------------------

    def run(self, task: str) -> list[EditResult]:
        """Plan then execute: convenience method."""
        plan = self.plan(task)
        return self.execute(plan)
