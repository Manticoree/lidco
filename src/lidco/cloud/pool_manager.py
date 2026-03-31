"""Q169 Task 960 — Agent Pool Manager."""
from __future__ import annotations

from dataclasses import dataclass

from lidco.cloud.agent_spawner import AgentSpawner
from lidco.cloud.status_tracker import AgentLog, StatusTracker


@dataclass
class PoolStats:
    """Pool statistics."""

    total: int
    running: int
    queued: int
    completed: int
    failed: int


class AgentPoolManager:
    """High-level manager coordinating spawner and tracker."""

    def __init__(
        self,
        spawner: AgentSpawner,
        tracker: StatusTracker,
        max_parallel: int = 4,
    ) -> None:
        self.spawner = spawner
        self.tracker = tracker
        self.max_parallel = max_parallel

    def submit(self, prompt: str, model: str = "") -> str:
        """Submit a new agent task. Returns agent_id."""
        handle = self.spawner.spawn(prompt, model=model)
        self.tracker.start_tracking(handle.agent_id)
        return handle.agent_id

    def cancel(self, agent_id: str) -> bool:
        """Cancel an agent."""
        ok = self.spawner.cancel(agent_id)
        if ok:
            self.tracker.fail(agent_id, "Cancelled by user")
        return ok

    def stats(self) -> PoolStats:
        """Return pool statistics."""
        agents = self.spawner.list_all()
        total = len(agents)
        running = sum(1 for a in agents if a.status == "running")
        queued = sum(1 for a in agents if a.status == "queued")
        completed = sum(1 for a in agents if a.status == "completed")
        failed = sum(1 for a in agents if a.status == "failed")
        return PoolStats(
            total=total,
            running=running,
            queued=queued,
            completed=completed,
            failed=failed,
        )

    def results(self, agent_id: str) -> AgentLog | None:
        """Return the log for an agent."""
        return self.tracker.get_log(agent_id)

    def drain(self) -> list[str]:
        """Wait for all agents to complete. Returns list of IDs."""
        return [a.agent_id for a in self.spawner.list_all()]

    def clear_completed(self) -> None:
        """Remove completed agents from the pool."""
        to_remove = [
            a.agent_id
            for a in self.spawner.list_all()
            if a.status in ("completed", "failed")
        ]
        for aid in to_remove:
            self.spawner._agents.pop(aid, None)
