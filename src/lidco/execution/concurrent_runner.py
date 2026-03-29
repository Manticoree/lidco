"""Q124 — ConcurrentRunner: run async tasks with concurrency control."""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class TaskSpec:
    id: str
    name: str
    fn: Callable  # async callable -> Any
    timeout: Optional[float] = None


@dataclass
class TaskOutcome:
    id: str
    name: str
    result: Any = None
    error: str = ""
    success: bool = True
    elapsed: float = 0.0


@dataclass
class RunReport:
    outcomes: list[TaskOutcome]
    total_elapsed: float

    @property
    def succeeded(self) -> int:
        return sum(1 for o in self.outcomes if o.success)

    @property
    def failed(self) -> int:
        return sum(1 for o in self.outcomes if not o.success)

    @property
    def success_rate(self) -> float:
        if not self.outcomes:
            return 0.0
        return self.succeeded / len(self.outcomes)


class ConcurrentRunner:
    def __init__(self, max_concurrency: int = 5) -> None:
        self.max_concurrency = max_concurrency

    async def run_all(self, tasks: list[TaskSpec]) -> RunReport:
        if not tasks:
            return RunReport(outcomes=[], total_elapsed=0.0)

        semaphore = asyncio.Semaphore(self.max_concurrency)
        start = time.monotonic()

        async def _run_one(spec: TaskSpec) -> TaskOutcome:
            async with semaphore:
                t0 = time.monotonic()
                try:
                    if spec.timeout is not None:
                        result = await asyncio.wait_for(spec.fn(), timeout=spec.timeout)
                    else:
                        result = await spec.fn()
                    elapsed = time.monotonic() - t0
                    return TaskOutcome(
                        id=spec.id,
                        name=spec.name,
                        result=result,
                        success=True,
                        elapsed=elapsed,
                    )
                except Exception as exc:
                    elapsed = time.monotonic() - t0
                    return TaskOutcome(
                        id=spec.id,
                        name=spec.name,
                        error=str(exc),
                        success=False,
                        elapsed=elapsed,
                    )

        outcomes = await asyncio.gather(*[_run_one(t) for t in tasks])
        total_elapsed = time.monotonic() - start
        return RunReport(outcomes=list(outcomes), total_elapsed=total_elapsed)

    def run_sync(self, tasks: list[TaskSpec]) -> RunReport:
        return asyncio.run(self.run_all(tasks))

    @staticmethod
    def make_task(name: str, fn: Callable, timeout: Optional[float] = None) -> TaskSpec:
        return TaskSpec(id=str(uuid.uuid4()), name=name, fn=fn, timeout=timeout)
