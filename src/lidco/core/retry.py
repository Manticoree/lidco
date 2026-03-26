"""Retry decorator and RetryPolicy (stdlib only)."""
from __future__ import annotations

import asyncio
import functools
import random
import time
from dataclasses import dataclass, field


@dataclass
class RetryPolicy:
    """
    Configuration for retry behaviour.

    Parameters
    ----------
    max_attempts:
        Total attempts (including the first try).
    backoff:
        Delay strategy: ``"exponential"``, ``"linear"``, or ``"fixed"``.
    base_delay:
        Base delay in seconds.
    max_delay:
        Upper bound on computed delay.
    jitter:
        Add up to 10 % random jitter to each delay.
    exceptions:
        Exception types to catch and retry on.
    """

    max_attempts: int = 3
    backoff: str = "exponential"
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: bool = True
    exceptions: tuple[type[Exception], ...] = (Exception,)

    def compute_delay(self, attempt: int) -> float:
        """Return delay for *attempt* (0-based: first retry = attempt 1)."""
        if self.backoff == "exponential":
            delay = self.base_delay * (2 ** attempt)
        elif self.backoff == "linear":
            delay = self.base_delay * (attempt + 1)
        else:  # fixed
            delay = self.base_delay

        delay = min(delay, self.max_delay)

        if self.jitter:
            delay += random.uniform(0, delay * 0.1)

        return delay


@dataclass
class RetryStats:
    attempts: int
    total_elapsed: float
    last_error: str | None
    success: bool


class RetryExhausted(Exception):
    """Raised when all retry attempts fail."""

    def __init__(self, stats: RetryStats, last_exception: Exception) -> None:
        super().__init__(
            f"Retry exhausted after {stats.attempts} attempt(s): {last_exception}"
        )
        self.stats = stats
        self.last_exception = last_exception


def retry(policy: RetryPolicy | None = None, **kwargs):
    """
    Decorator for sync functions.

    Usage::

        @retry(RetryPolicy(max_attempts=3))
        def flaky() -> str: ...

        @retry(max_attempts=5, backoff="linear")
        def another() -> None: ...
    """
    if policy is None:
        policy = RetryPolicy(**kwargs)

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kw):
            return retry_call(fn, *args, policy=policy, **kw)
        return wrapper

    return decorator


def retry_async(policy: RetryPolicy | None = None, **kwargs):
    """
    Decorator for async functions.

    Usage::

        @retry_async(RetryPolicy(max_attempts=3))
        async def flaky() -> str: ...
    """
    if policy is None:
        policy = RetryPolicy(**kwargs)

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kw):
            start = time.monotonic()
            last_exc: Exception | None = None

            for attempt in range(policy.max_attempts):
                try:
                    return await fn(*args, **kw)
                except policy.exceptions as exc:
                    last_exc = exc
                    if attempt < policy.max_attempts - 1:
                        delay = policy.compute_delay(attempt)
                        await asyncio.sleep(delay)

            elapsed = time.monotonic() - start
            stats = RetryStats(
                attempts=policy.max_attempts,
                total_elapsed=elapsed,
                last_error=str(last_exc),
                success=False,
            )
            raise RetryExhausted(stats, last_exc)  # type: ignore[arg-type]

        return wrapper

    return decorator


def retry_call(fn, *args, policy: RetryPolicy | None = None, **kwargs) -> object:
    """
    Non-decorator form: call *fn* with retry logic.

    Parameters
    ----------
    fn:
        Callable to retry.
    *args:
        Positional arguments forwarded to *fn*.
    policy:
        RetryPolicy instance.  Defaults to ``RetryPolicy()`` if None.
    **kwargs:
        Keyword arguments forwarded to *fn*.

    Returns
    -------
    object
        Return value of *fn* on success.

    Raises
    ------
    RetryExhausted
        If all attempts fail.
    """
    if policy is None:
        policy = RetryPolicy()

    start = time.monotonic()
    last_exc: Exception | None = None

    for attempt in range(policy.max_attempts):
        try:
            return fn(*args, **kwargs)
        except policy.exceptions as exc:
            last_exc = exc
            if attempt < policy.max_attempts - 1:
                delay = policy.compute_delay(attempt)
                time.sleep(delay)

    elapsed = time.monotonic() - start
    stats = RetryStats(
        attempts=policy.max_attempts,
        total_elapsed=elapsed,
        last_error=str(last_exc),
        success=False,
    )
    raise RetryExhausted(stats, last_exc)  # type: ignore[arg-type]
