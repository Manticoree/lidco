"""RetryExecutor — sync/async retry with exponential backoff (stdlib only)."""
from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class RetryConfig:
    """Configuration for retry behaviour."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    backoff_factor: float = 2.0
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,)


@dataclass
class RetryResult:
    """Result of a retry execution."""

    success: bool
    result: Any
    attempts: int
    total_time: float
    last_error: Optional[Exception] = None


class RetryExecutor:
    """Execute callables with configurable retry and exponential backoff."""

    def __init__(self, config: RetryConfig | None = None) -> None:
        self._config = config or RetryConfig()
        self._total_executions = 0
        self._total_retries = 0
        self._total_failures = 0

    def execute(self, fn, *args, **kwargs) -> RetryResult:
        """Sync retry with exponential backoff."""
        start = time.monotonic()
        last_error: Exception | None = None
        attempts = 0

        for attempt in range(self._config.max_retries + 1):
            attempts = attempt + 1
            try:
                result = fn(*args, **kwargs)
                elapsed = time.monotonic() - start
                self._total_executions += 1
                if attempt > 0:
                    self._total_retries += attempt
                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempts,
                    total_time=elapsed,
                )
            except self._config.retryable_exceptions as exc:
                last_error = exc
                if attempt < self._config.max_retries:
                    delay = self._calculate_delay(attempt)
                    time.sleep(delay)

        elapsed = time.monotonic() - start
        self._total_executions += 1
        self._total_retries += self._config.max_retries
        self._total_failures += 1
        return RetryResult(
            success=False,
            result=None,
            attempts=attempts,
            total_time=elapsed,
            last_error=last_error,
        )

    async def async_execute(self, fn, *args, **kwargs) -> RetryResult:
        """Async retry with exponential backoff."""
        start = time.monotonic()
        last_error: Exception | None = None
        attempts = 0

        for attempt in range(self._config.max_retries + 1):
            attempts = attempt + 1
            try:
                result = await fn(*args, **kwargs)
                elapsed = time.monotonic() - start
                self._total_executions += 1
                if attempt > 0:
                    self._total_retries += attempt
                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempts,
                    total_time=elapsed,
                )
            except self._config.retryable_exceptions as exc:
                last_error = exc
                if attempt < self._config.max_retries:
                    delay = self._calculate_delay(attempt)
                    await asyncio.sleep(delay)

        elapsed = time.monotonic() - start
        self._total_executions += 1
        self._total_retries += self._config.max_retries
        self._total_failures += 1
        return RetryResult(
            success=False,
            result=None,
            attempts=attempts,
            total_time=elapsed,
            last_error=last_error,
        )

    def _calculate_delay(self, attempt: int) -> float:
        """Return min(base * factor^attempt, max_delay) with jitter."""
        delay = self._config.base_delay * (self._config.backoff_factor ** attempt)
        delay = min(delay, self._config.max_delay)
        # Add up to 10% jitter
        delay += random.uniform(0, delay * 0.1)
        return delay

    def reset_stats(self) -> None:
        """Reset execution statistics."""
        self._total_executions = 0
        self._total_retries = 0
        self._total_failures = 0

    @property
    def stats(self) -> dict:
        """Return execution statistics."""
        return {
            "total_executions": self._total_executions,
            "total_retries": self._total_retries,
            "total_failures": self._total_failures,
        }
