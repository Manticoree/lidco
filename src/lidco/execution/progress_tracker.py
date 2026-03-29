"""Q124 — ProgressTracker: track status of running tasks."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProgressEntry:
    id: str
    name: str
    status: str  # "pending" / "running" / "done" / "failed"
    started_at: Optional[float] = None
    finished_at: Optional[float] = None

    @property
    def elapsed(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.finished_at if self.finished_at is not None else time.monotonic()
        return end - self.started_at


class ProgressTracker:
    def __init__(self) -> None:
        self._entries: dict[str, ProgressEntry] = {}

    def start(self, id: str, name: str) -> ProgressEntry:
        entry = ProgressEntry(
            id=id,
            name=name,
            status="running",
            started_at=time.monotonic(),
        )
        self._entries[id] = entry
        return entry

    def finish(self, id: str, success: bool = True) -> ProgressEntry:
        entry = self._entries[id]
        entry.status = "done" if success else "failed"
        entry.finished_at = time.monotonic()
        return entry

    def get(self, id: str) -> Optional[ProgressEntry]:
        return self._entries.get(id)

    def list_all(self) -> list[ProgressEntry]:
        return list(self._entries.values())

    def summary(self) -> dict:
        entries = list(self._entries.values())
        return {
            "total": len(entries),
            "done": sum(1 for e in entries if e.status == "done"),
            "running": sum(1 for e in entries if e.status == "running"),
            "failed": sum(1 for e in entries if e.status == "failed"),
            "pending": sum(1 for e in entries if e.status == "pending"),
        }

    def clear(self) -> None:
        self._entries.clear()
