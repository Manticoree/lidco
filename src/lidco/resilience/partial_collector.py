"""PartialCollector — collect results even when some tasks fail (stdlib only)."""
from __future__ import annotations

import asyncio
import concurrent.futures
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class CollectionItem:
    """A single collected result."""

    key: str
    value: Any
    error: Optional[str] = None
    success: bool = True


@dataclass
class CollectionResult:
    """Aggregated collection outcome."""

    items: list[CollectionItem] = field(default_factory=list)
    succeeded: int = 0
    failed: int = 0
    partial: bool = False


class PartialCollector:
    """Run multiple tasks and collect results even if some fail."""

    def __init__(self) -> None:
        self._last_result: CollectionResult | None = None

    def collect(self, tasks: dict[str, Callable]) -> CollectionResult:
        """Run all tasks (sync), collecting results regardless of failures."""
        items: list[CollectionItem] = []
        succeeded = 0
        failed = 0

        for key, fn in tasks.items():
            try:
                value = fn()
                items.append(CollectionItem(key=key, value=value, success=True))
                succeeded += 1
            except Exception as exc:
                items.append(CollectionItem(
                    key=key, value=None, error=str(exc), success=False,
                ))
                failed += 1

        result = CollectionResult(
            items=items,
            succeeded=succeeded,
            failed=failed,
            partial=failed > 0 and succeeded > 0,
        )
        self._last_result = result
        return result

    async def async_collect(self, tasks: dict[str, Callable]) -> CollectionResult:
        """Run all tasks (async), collecting results regardless of failures."""
        items: list[CollectionItem] = []
        succeeded = 0
        failed = 0

        for key, fn in tasks.items():
            try:
                value = await fn()
                items.append(CollectionItem(key=key, value=value, success=True))
                succeeded += 1
            except Exception as exc:
                items.append(CollectionItem(
                    key=key, value=None, error=str(exc), success=False,
                ))
                failed += 1

        result = CollectionResult(
            items=items,
            succeeded=succeeded,
            failed=failed,
            partial=failed > 0 and succeeded > 0,
        )
        self._last_result = result
        return result

    def collect_with_timeout(self, tasks: dict[str, Callable], timeout: float) -> CollectionResult:
        """Run all tasks with a per-task timeout."""
        items: list[CollectionItem] = []
        succeeded = 0
        failed = 0

        for key, fn in tasks.items():
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(fn)
                    value = future.result(timeout=timeout)
                items.append(CollectionItem(key=key, value=value, success=True))
                succeeded += 1
            except concurrent.futures.TimeoutError:
                items.append(CollectionItem(
                    key=key, value=None, error="Timeout", success=False,
                ))
                failed += 1
            except Exception as exc:
                items.append(CollectionItem(
                    key=key, value=None, error=str(exc), success=False,
                ))
                failed += 1

        result = CollectionResult(
            items=items,
            succeeded=succeeded,
            failed=failed,
            partial=failed > 0 and succeeded > 0,
        )
        self._last_result = result
        return result

    @property
    def success_rate(self) -> float:
        """Return success rate of last collection (0.0–1.0)."""
        if self._last_result is None:
            return 0.0
        total = self._last_result.succeeded + self._last_result.failed
        if total == 0:
            return 0.0
        return self._last_result.succeeded / total
