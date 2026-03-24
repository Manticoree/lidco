"""Managed async worker pool for sub-agent task delegation (Devin 2.0 parity)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, TypeVar

T = TypeVar("T")


@dataclass
class WorkItem:
    name: str
    coro: Any  # coroutine object
    timeout: float | None = None


@dataclass
class WorkResult:
    name: str
    success: bool
    result: Any = None
    error: str = ""


@dataclass
class PoolResult:
    results: list[WorkResult]
    successful: int
    failed: int
    cancelled: int = 0

    @property
    def all_success(self) -> bool:
        return self.failed == 0 and self.cancelled == 0

    def get(self, name: str) -> WorkResult | None:
        for r in self.results:
            if r.name == name:
                return r
        return None

    def format_summary(self) -> str:
        lines = [f"Pool: {self.successful} ok, {self.failed} failed, {self.cancelled} cancelled"]
        for r in self.results:
            icon = "v" if r.success else "x"
            summary = str(r.result)[:50] if r.result is not None else r.error[:50]
            lines.append(f"  {icon} {r.name}: {summary}")
        return "\n".join(lines)


class WorkerPool:
    """Run a collection of async tasks with concurrency limiting and timeout support.

    Inspired by Devin 2.0's "managed Devin teams" — each task is independent
    and results are aggregated after all tasks finish.
    """

    def __init__(self, max_workers: int = 4, default_timeout: float | None = 300.0) -> None:
        self.max_workers = max_workers
        self.default_timeout = default_timeout
        self._semaphore: asyncio.Semaphore | None = None

    async def _run_item(self, item: WorkItem) -> WorkResult:
        sem = self._semaphore
        if sem is None:
            sem = asyncio.Semaphore(self.max_workers)
        timeout = item.timeout if item.timeout is not None else self.default_timeout
        try:
            async with sem:
                if timeout is not None:
                    result = await asyncio.wait_for(item.coro, timeout=timeout)
                else:
                    result = await item.coro
            return WorkResult(name=item.name, success=True, result=result)
        except asyncio.TimeoutError:
            return WorkResult(name=item.name, success=False, error=f"timed out after {timeout}s")
        except asyncio.CancelledError:
            return WorkResult(name=item.name, success=False, error="cancelled")
        except Exception as e:
            return WorkResult(name=item.name, success=False, error=str(e))

    async def run_all(self, items: list[WorkItem]) -> PoolResult:
        """Run all work items concurrently (up to max_workers at a time)."""
        if not items:
            return PoolResult(results=[], successful=0, failed=0)
        self._semaphore = asyncio.Semaphore(self.max_workers)
        tasks = [asyncio.create_task(self._run_item(item)) for item in items]
        results: list[WorkResult] = list(await asyncio.gather(*tasks))
        successful = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success and "cancelled" not in r.error)
        cancelled = sum(1 for r in results if "cancelled" in r.error)
        return PoolResult(results=results, successful=successful, failed=failed, cancelled=cancelled)

    async def submit_one(
        self,
        name: str,
        coro: Any,
        timeout: float | None = None,
    ) -> WorkResult:
        """Run a single coroutine with timeout."""
        item = WorkItem(name=name, coro=coro, timeout=timeout)
        return await self._run_item(item)

    def run_sync(self, items: list[WorkItem]) -> PoolResult:
        """Synchronous wrapper around run_all."""
        return asyncio.run(self.run_all(items))
