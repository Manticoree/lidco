"""Batch task decomposition and parallel execution — Task 288.

Decomposes a large task into N independent units and runs each
as a background agent (optionally in isolated git worktrees).

Usage::

    batch = BatchProcessor(session)
    job = await batch.run("add tests for all 20 public functions in auth.py")
    print(job.summary())
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lidco.core.session import Session

logger = logging.getLogger(__name__)

_DECOMPOSE_PROMPT = """\
You are a task planner. Decompose the following large task into {n} independent, \
parallelizable sub-tasks. Each sub-task must be:
- Self-contained (can run independently)
- Specific and actionable
- Roughly equal in size

Output ONLY a numbered list, one sub-task per line. No explanation.

Task: {task}
"""


@dataclass
class BatchUnit:
    """A single unit of work within a batch job."""

    index: int
    task: str
    status: str = "pending"    # pending | running | done | failed
    result: str = ""
    error: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass
class BatchJob:
    """A batch decomposition job."""

    original_task: str
    units: list[BatchUnit] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def n_done(self) -> int:
        return sum(1 for u in self.units if u.status == "done")

    @property
    def n_failed(self) -> int:
        return sum(1 for u in self.units if u.status == "failed")

    @property
    def n_running(self) -> int:
        return sum(1 for u in self.units if u.status == "running")

    @property
    def complete(self) -> bool:
        return all(u.status in ("done", "failed") for u in self.units)

    def summary(self) -> str:
        total = len(self.units)
        lines = [
            f"**Batch: {self.original_task[:60]}**\n",
            f"Units: {total} total | {self.n_done} done | {self.n_failed} failed | {self.n_running} running",
        ]
        for u in self.units:
            icon = {"pending": "⏳", "running": "🔄", "done": "✅", "failed": "❌"}.get(u.status, "?")
            lines.append(f"  {icon} [{u.index}] {u.task[:70]}")
            if u.error:
                lines.append(f"      Error: {u.error[:100]}")
        return "\n".join(lines)


class BatchProcessor:
    """Decomposes tasks and runs them in parallel as background agents.

    Args:
        session: Active LIDCO session.
        max_concurrent: Maximum number of units to run simultaneously.
        n_units: Default number of sub-tasks to decompose into.
    """

    def __init__(
        self,
        session: "Session",
        max_concurrent: int = 4,
        n_units: int = 5,
    ) -> None:
        self._session = session
        self._max_concurrent = max_concurrent
        self._n_units = n_units

    async def decompose(self, task: str, n: int | None = None) -> list[str]:
        """Use LLM to split *task* into *n* independent sub-tasks."""
        n = n or self._n_units
        prompt = _DECOMPOSE_PROMPT.format(task=task, n=n)
        try:
            response = await self._session.orchestrator.handle(
                prompt,
                agent_name=None,
            )
            content = response.content if hasattr(response, "content") else str(response)
        except Exception as exc:
            logger.warning("BatchProcessor: decompose failed: %s", exc)
            return [task]  # fallback: single unit

        # Parse numbered list
        import re
        units: list[str] = []
        for line in content.splitlines():
            line = line.strip()
            m = re.match(r"^(\d+)[.)]\s+(.+)", line)
            if m:
                units.append(m.group(2).strip())
        return units if units else [task]

    async def run(
        self,
        task: str,
        n: int | None = None,
        agent_name: str | None = None,
        status_callback: Any = None,
    ) -> BatchJob:
        """Decompose *task* and run all units in parallel.

        Args:
            task: The main task to decompose.
            n: Number of sub-units (default: self._n_units).
            agent_name: Agent to use for each unit.
            status_callback: Called with (unit_index, status, message).
        """
        sub_tasks = await self.decompose(task, n=n)
        job = BatchJob(original_task=task)
        for i, t in enumerate(sub_tasks, 1):
            job.units.append(BatchUnit(index=i, task=t))

        if status_callback:
            status_callback(-1, "decomposed", f"Split into {len(sub_tasks)} units")

        semaphore = asyncio.Semaphore(self._max_concurrent)

        async def _run_unit(unit: BatchUnit) -> None:
            async with semaphore:
                unit.status = "running"
                unit.started_at = datetime.now(timezone.utc)
                if status_callback:
                    status_callback(unit.index, "running", unit.task[:60])
                try:
                    response = await self._session.orchestrator.handle(
                        unit.task,
                        agent_name=agent_name,
                    )
                    unit.result = response.content if hasattr(response, "content") else str(response)
                    unit.status = "done"
                    if status_callback:
                        status_callback(unit.index, "done", unit.task[:60])
                except Exception as exc:
                    unit.status = "failed"
                    unit.error = str(exc)
                    if status_callback:
                        status_callback(unit.index, "failed", str(exc)[:80])
                finally:
                    unit.finished_at = datetime.now(timezone.utc)

        await asyncio.gather(*[_run_unit(u) for u in job.units])
        return job
