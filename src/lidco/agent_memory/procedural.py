"""Procedural memory — stores learned procedures with step sequences.

Tracks preconditions, steps, and success rates so the agent can reuse
proven procedures and avoid failed ones.
"""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from typing import List


@dataclass
class Procedure:
    """A recorded procedure."""

    id: str
    task_type: str
    name: str
    steps: List[str] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    timestamp: float = field(default_factory=time.time)

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / total

    @property
    def total_attempts(self) -> int:
        return self.success_count + self.failure_count


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower()))


class ProceduralMemory:
    """Store and query learned procedures."""

    def __init__(self) -> None:
        self._procedures: dict[str, Procedure] = {}

    def record(self, procedure: dict) -> Procedure:
        """Record a procedure from a dict.

        Required keys: task_type, name, steps.
        Optional keys: preconditions.
        """
        if not procedure.get("task_type"):
            raise ValueError("task_type is required")
        if not procedure.get("name"):
            raise ValueError("name is required")
        if not procedure.get("steps"):
            raise ValueError("steps is required and must be non-empty")

        proc = Procedure(
            id=uuid.uuid4().hex[:12],
            task_type=procedure["task_type"],
            name=procedure["name"],
            steps=list(procedure["steps"]),
            preconditions=list(procedure.get("preconditions", [])),
            timestamp=procedure.get("timestamp", time.time()),
        )
        self._procedures[proc.id] = proc
        return proc

    def find(self, task_type: str) -> list[Procedure]:
        """Find procedures matching *task_type* (case-insensitive substring)."""
        task_lower = task_type.lower()
        results = [
            p for p in self._procedures.values()
            if task_lower in p.task_type.lower()
        ]
        results.sort(key=lambda p: p.success_rate, reverse=True)
        return results

    def update_success_rate(self, proc_id: str, success: bool) -> Procedure:
        """Update success/failure count for a procedure."""
        if proc_id not in self._procedures:
            raise KeyError(f"Procedure {proc_id!r} not found")
        proc = self._procedures[proc_id]
        if success:
            proc.success_count += 1
        else:
            proc.failure_count += 1
        return proc

    def generalize(self) -> list[Procedure]:
        """Return procedures with success_rate >= 0.7 and at least 2 attempts.

        These are considered reliable enough to generalize.
        """
        return [
            p for p in self._procedures.values()
            if p.total_attempts >= 2 and p.success_rate >= 0.7
        ]

    def all(self) -> list[Procedure]:
        """Return all procedures."""
        return list(self._procedures.values())
