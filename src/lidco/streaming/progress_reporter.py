"""Structured progress reporting for long-running operations."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProgressEntry:
    """Snapshot of progress for a single task."""

    task: str
    current: int = 0
    total: int = 0
    phase: str = ""
    message: str = ""
    timestamp: float = field(default_factory=time.time)
    parent_task: str = ""


class ProgressReporter:
    """Track progress of multiple (possibly nested) tasks."""

    def __init__(self) -> None:
        self._entries: dict[str, ProgressEntry] = {}

    def start(self, task: str, total: int = 0, phase: str = "") -> ProgressEntry:
        """Register a new task and return its initial entry."""
        entry = ProgressEntry(task=task, current=0, total=total, phase=phase)
        self._entries = {**self._entries, task: entry}
        return entry

    def update(
        self,
        task: str,
        current: int,
        message: str = "",
        phase: str = "",
    ) -> ProgressEntry | None:
        """Update progress for *task*.  Returns ``None`` if unknown."""
        prev = self._entries.get(task)
        if prev is None:
            return None
        entry = ProgressEntry(
            task=task,
            current=current,
            total=prev.total,
            phase=phase or prev.phase,
            message=message or prev.message,
            parent_task=prev.parent_task,
        )
        self._entries = {**self._entries, task: entry}
        return entry

    def complete(self, task: str, message: str = "done") -> ProgressEntry | None:
        """Mark *task* as complete.  Returns ``None`` if unknown."""
        prev = self._entries.get(task)
        if prev is None:
            return None
        entry = ProgressEntry(
            task=task,
            current=prev.total if prev.total > 0 else prev.current,
            total=prev.total,
            phase="complete",
            message=message,
            parent_task=prev.parent_task,
        )
        self._entries = {**self._entries, task: entry}
        return entry

    def percentage(self, task: str) -> float:
        """Return 0.0–100.0 progress percentage for *task*."""
        entry = self._entries.get(task)
        if entry is None or entry.total <= 0:
            return 0.0
        return min(100.0, (entry.current / entry.total) * 100.0)

    def eta(self, task: str) -> float | None:
        """Estimated seconds remaining, or ``None`` if not enough data."""
        entry = self._entries.get(task)
        if entry is None or entry.total <= 0 or entry.current <= 0:
            return None
        elapsed = time.time() - entry.timestamp
        rate = entry.current / max(elapsed, 0.001)
        remaining = entry.total - entry.current
        if remaining <= 0:
            return 0.0
        return remaining / rate

    def start_subtask(
        self,
        parent: str,
        subtask: str,
        total: int = 0,
    ) -> ProgressEntry:
        """Create a subtask linked to *parent*."""
        entry = ProgressEntry(
            task=subtask,
            current=0,
            total=total,
            parent_task=parent,
        )
        self._entries = {**self._entries, subtask: entry}
        return entry

    def get_active(self) -> list[ProgressEntry]:
        """Return entries that are not yet complete."""
        return [
            e
            for e in self._entries.values()
            if e.total <= 0 or e.current < e.total
        ]

    def summary(self) -> str:
        """Human-readable summary of all tracked tasks."""
        if not self._entries:
            return "No progress entries."
        lines: list[str] = []
        for entry in self._entries.values():
            pct = self.percentage(entry.task)
            status = f"{entry.current}/{entry.total}" if entry.total > 0 else str(entry.current)
            label = f"  [{entry.phase}]" if entry.phase else ""
            lines.append(f"{entry.task}: {status} ({pct:.1f}%){label}")
        return "\n".join(lines)
