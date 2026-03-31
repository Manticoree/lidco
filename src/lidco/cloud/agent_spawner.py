"""Q169 Task 957 — Background Agent Spawner."""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class AgentHandle:
    """Handle representing a background agent."""

    agent_id: str
    prompt: str
    model: str
    status: str  # queued | running | completed | failed
    created_at: float
    worktree_path: str | None = None
    branch_name: str | None = None


class AgentSpawner:
    """Spawns and manages background agent handles."""

    def __init__(
        self,
        max_concurrent: int = 4,
        worktree_base: str = ".lidco/worktrees",
    ) -> None:
        self.max_concurrent = max_concurrent
        self.worktree_base = worktree_base
        self._agents: dict[str, AgentHandle] = {}

    def spawn(
        self,
        prompt: str,
        model: str = "",
        repo_dir: str = ".",
    ) -> AgentHandle:
        """Create a new agent handle in queued state."""
        agent_id = uuid.uuid4().hex[:12]
        branch = self._generate_branch_name(prompt)
        handle = AgentHandle(
            agent_id=agent_id,
            prompt=prompt,
            model=model,
            status="queued",
            created_at=time.time(),
            worktree_path=f"{self.worktree_base}/{agent_id}",
            branch_name=branch,
        )
        self._agents[agent_id] = handle
        return handle

    def start(
        self,
        agent_id: str,
        execute_fn: Optional[Callable[..., Any]] = None,
    ) -> AgentHandle:
        """Mark agent as running and optionally execute."""
        handle = self._agents.get(agent_id)
        if handle is None:
            raise KeyError(f"Unknown agent: {agent_id}")
        updated = AgentHandle(
            agent_id=handle.agent_id,
            prompt=handle.prompt,
            model=handle.model,
            status="running",
            created_at=handle.created_at,
            worktree_path=handle.worktree_path,
            branch_name=handle.branch_name,
        )
        self._agents[agent_id] = updated
        if execute_fn is not None:
            try:
                execute_fn(updated)
                completed = AgentHandle(
                    agent_id=updated.agent_id,
                    prompt=updated.prompt,
                    model=updated.model,
                    status="completed",
                    created_at=updated.created_at,
                    worktree_path=updated.worktree_path,
                    branch_name=updated.branch_name,
                )
                self._agents[agent_id] = completed
                return completed
            except Exception:
                failed = AgentHandle(
                    agent_id=updated.agent_id,
                    prompt=updated.prompt,
                    model=updated.model,
                    status="failed",
                    created_at=updated.created_at,
                    worktree_path=updated.worktree_path,
                    branch_name=updated.branch_name,
                )
                self._agents[agent_id] = failed
                return failed
        return updated

    def get(self, agent_id: str) -> AgentHandle | None:
        """Return agent handle or None."""
        return self._agents.get(agent_id)

    def cancel(self, agent_id: str) -> bool:
        """Cancel a queued or running agent. Returns True if cancelled."""
        handle = self._agents.get(agent_id)
        if handle is None:
            return False
        if handle.status in ("completed", "failed"):
            return False
        cancelled = AgentHandle(
            agent_id=handle.agent_id,
            prompt=handle.prompt,
            model=handle.model,
            status="failed",
            created_at=handle.created_at,
            worktree_path=handle.worktree_path,
            branch_name=handle.branch_name,
        )
        self._agents[agent_id] = cancelled
        return True

    def list_all(self) -> list[AgentHandle]:
        """Return all agent handles."""
        return list(self._agents.values())

    def _generate_branch_name(self, prompt: str) -> str:
        """Generate a branch name from the prompt text."""
        slug = re.sub(r"[^a-z0-9]+", "-", prompt.lower().strip())
        slug = slug.strip("-")[:40]
        if not slug:
            slug = "agent-task"
        return f"agent/{slug}"
