"""Q169 Task 958 — Agent Status Tracker."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class AgentLog:
    """Log of an agent's execution."""

    agent_id: str
    entries: list[str] = field(default_factory=list)
    output: str = ""
    diff: str = ""
    started_at: float = 0.0
    finished_at: float | None = None
    error: str = ""


class StatusTracker:
    """Tracks status and logs for background agents."""

    def __init__(self, max_history: int = 100) -> None:
        self.max_history = max_history
        self._logs: dict[str, AgentLog] = {}
        self._running: set[str] = set()
        self._completed: set[str] = set()

    def start_tracking(self, agent_id: str) -> None:
        """Begin tracking an agent."""
        log = AgentLog(agent_id=agent_id, started_at=time.time())
        self._logs[agent_id] = log
        self._running.add(agent_id)
        self._trim()

    def log(self, agent_id: str, message: str) -> None:
        """Append a log entry."""
        agent_log = self._logs.get(agent_id)
        if agent_log is None:
            return
        agent_log.entries.append(message)

    def complete(self, agent_id: str, output: str, diff: str = "") -> None:
        """Mark agent as completed."""
        agent_log = self._logs.get(agent_id)
        if agent_log is None:
            return
        agent_log.output = output
        agent_log.diff = diff
        agent_log.finished_at = time.time()
        self._running.discard(agent_id)
        self._completed.add(agent_id)

    def fail(self, agent_id: str, error: str) -> None:
        """Mark agent as failed."""
        agent_log = self._logs.get(agent_id)
        if agent_log is None:
            return
        agent_log.error = error
        agent_log.finished_at = time.time()
        self._running.discard(agent_id)

    def get_log(self, agent_id: str) -> AgentLog | None:
        """Return log for an agent."""
        return self._logs.get(agent_id)

    def running(self) -> list[str]:
        """Return IDs of agents currently running."""
        return sorted(self._running)

    def completed(self) -> list[str]:
        """Return IDs of completed agents."""
        return sorted(self._completed)

    def summary(self) -> dict:
        """Return summary statistics."""
        total = len(self._logs)
        running_count = len(self._running)
        completed_count = len(self._completed)
        failed_count = sum(
            1 for log in self._logs.values()
            if log.error and log.agent_id not in self._running
        )
        return {
            "total": total,
            "running": running_count,
            "completed": completed_count,
            "failed": failed_count,
        }

    def _trim(self) -> None:
        """Remove oldest finished entries if over max_history."""
        if len(self._logs) <= self.max_history:
            return
        finished = [
            (aid, log)
            for aid, log in self._logs.items()
            if aid not in self._running
        ]
        finished.sort(key=lambda x: x[1].started_at)
        while len(self._logs) > self.max_history and finished:
            aid, _ = finished.pop(0)
            del self._logs[aid]
            self._completed.discard(aid)
