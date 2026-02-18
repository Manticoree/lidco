"""Retry with exponential backoff for LLM calls."""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, TypeVar

from litellm.exceptions import (
    APIConnectionError,
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
    APIConnectionError,
    InternalServerError,
)


@dataclass(frozen=True)
class RetryConfig:
    """Configuration for retry with exponential backoff."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: bool = True
    retryable_exceptions: tuple[type[BaseException], ...] = field(
        default_factory=lambda: RETRYABLE_EXCEPTIONS,
    )


async def with_retry(
    fn: Callable[[], Awaitable[T]],
    config: RetryConfig,
) -> T:
    """Execute an async callable with exponential backoff retry.

    Retries only on exceptions listed in ``config.retryable_exceptions``.
    Non-retryable exceptions propagate immediately.
    """
    last_error: BaseException | None = None

    for attempt in range(config.max_retries + 1):
        try:
            return await fn()
        except tuple(config.retryable_exceptions) as exc:
            last_error = exc
            if attempt == config.max_retries:
                raise

            delay = min(config.base_delay * (2 ** attempt), config.max_delay)
            if config.jitter:
                delay *= random.uniform(0.5, 1.5)

            logger.warning(
                "Retry %d/%d after %.1fs: %s",
                attempt + 1,
                config.max_retries,
                delay,
                exc,
            )
            await asyncio.sleep(delay)

    # Unreachable, but satisfies type checker
    raise last_error  # type: ignore[misc]
