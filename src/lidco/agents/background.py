"""Background agent execution — Task 270.

Allows agents to run in the background while the REPL remains interactive.
Completed tasks are stored and can be queried via ``/agents``.

Usage::

    mgr = BackgroundTaskManager(session)
    task_id = mgr.submit("refactor utils.py", agent_name="refactor")
    # ... user continues chatting ...
    done = mgr.collect_done()   # returns finished tasks
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lidco.agents.base import AgentResponse
    from lidco.core.session import Session

logger = logging.getLogger(__name__)


@dataclass
class BackgroundAgent:
    """Metadata and result for a background agent task."""

    task_id: str
    task: str
    agent_name: str | None
    started_at: datetime
    status: str = "running"      # "running" | "done" | "failed" | "cancelled"
    result: "AgentResponse | None" = None
    error: str | None = None
    finished_at: datetime | None = None
    worktree_branch: str | None = None   # set when isolation=worktree and changes exist


class BackgroundTaskManager:
    """Manages background agent tasks for a LIDCO session.

    Tasks are submitted as asyncio.Task objects.  When completed, they
    move from ``_running`` to ``_done``.

    Thread-safety: designed for single-event-loop use; all access from
    the REPL async context.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}      # task_id → asyncio.Task
        self._agents: dict[str, BackgroundAgent] = {}  # task_id → metadata
        self._notification_callback: Any = None

    def set_notification_callback(self, cb: Any) -> None:
        """Called with ``(BackgroundAgent,)`` when a task finishes."""
        self._notification_callback = cb

    def submit(
        self,
        task: str,
        session: "Session",
        agent_name: str | None = None,
    ) -> str:
        """Submit a task to run in the background.

        Returns the task_id that can be used to query status.
        """
        task_id = uuid.uuid4().hex[:8]
        bg = BackgroundAgent(
            task_id=task_id,
            task=task,
            agent_name=agent_name,
            started_at=datetime.now(timezone.utc),
        )
        self._agents[task_id] = bg

        async def _run() -> None:
            try:
                context = session.get_full_context()
                response = await session.orchestrator.handle(
                    task,
                    agent_name=agent_name,
                    context=context,
                )
                if hasattr(response, "content"):
                    bg.result = response
                bg.status = "done"
            except asyncio.CancelledError:
                bg.status = "cancelled"
            except Exception as exc:
                bg.status = "failed"
                bg.error = str(exc)
                logger.debug("Background task '%s' failed: %s", task_id, exc)
            finally:
                bg.finished_at = datetime.now(timezone.utc)
                self._tasks.pop(task_id, None)
                if self._notification_callback:
                    try:
                        self._notification_callback(bg)
                    except Exception:
                        pass

        coro_task = asyncio.ensure_future(_run())
        self._tasks[task_id] = coro_task
        logger.info("Background task '%s' submitted: %.60s", task_id, task)
        return task_id

    def cancel(self, task_id: str) -> bool:
        """Cancel a running background task. Returns True if found and cancelled."""
        task = self._tasks.get(task_id)
        if task and not task.done():
            task.cancel()
            bg = self._agents.get(task_id)
            if bg:
                bg.status = "cancelled"
            return True
        return False

    def get(self, task_id: str) -> BackgroundAgent | None:
        """Return metadata for *task_id*, or None if not found."""
        return self._agents.get(task_id)

    def list_all(self) -> list[BackgroundAgent]:
        """Return all tasks (running + finished) sorted by start time."""
        return sorted(self._agents.values(), key=lambda b: b.started_at)

    def list_running(self) -> list[BackgroundAgent]:
        return [b for b in self._agents.values() if b.status == "running"]

    def list_done(self) -> list[BackgroundAgent]:
        return [b for b in self._agents.values() if b.status in ("done", "failed", "cancelled")]

    def collect_done(self) -> list[BackgroundAgent]:
        """Return and remove all finished tasks from the registry."""
        done = self.list_done()
        for bg in done:
            self._agents.pop(bg.task_id, None)
        return done

    def running_count(self) -> int:
        return len(self.list_running())
