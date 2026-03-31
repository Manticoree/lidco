"""Adaptive retry with exponential backoff, jitter, and circuit breaking."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict


class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open for a function."""


@dataclass
class _FunctionStats:
    """Per-function failure tracking."""

    total_calls: int = 0
    total_failures: int = 0
    total_successes: int = 0
    consecutive_failures: int = 0
    circuit_open: bool = False
    last_failure_time: float = 0.0


class AdaptiveRetry:
    """Retry with exponential backoff, jitter, and per-function circuit breaking.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Base delay in seconds for exponential backoff.
        max_delay: Maximum delay cap in seconds.
        circuit_break_threshold: Consecutive failures before opening circuit.
        sleep_fn: Callable for sleeping (injectable for tests).
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        circuit_break_threshold: int = 5,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._circuit_break_threshold = circuit_break_threshold
        self._sleep_fn = sleep_fn or time.sleep
        self._stats: dict[str, _FunctionStats] = {}

    def _get_stats(self, fn_name: str) -> _FunctionStats:
        if fn_name not in self._stats:
            self._stats[fn_name] = _FunctionStats()
        return self._stats[fn_name]

    def _compute_delay(self, attempt: int) -> float:
        """Exponential backoff with jitter."""
        delay = self._base_delay * (2 ** attempt)
        delay = min(delay, self._max_delay)
        jitter = random.uniform(0, delay * 0.5)
        return delay + jitter

    def execute(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute fn with retries, backoff, and circuit breaking.

        Args:
            fn: The function to execute.
            *args: Positional arguments for fn.
            **kwargs: Keyword arguments for fn.

        Returns:
            The return value of fn on success.

        Raises:
            CircuitOpenError: If the circuit breaker is open.
            Exception: The last exception if all retries are exhausted.
        """
        fn_name = getattr(fn, "__name__", str(fn))
        stats = self._get_stats(fn_name)

        if stats.circuit_open:
            raise CircuitOpenError(
                f"Circuit open for {fn_name!r} after "
                f"{stats.consecutive_failures} consecutive failures"
            )

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            stats.total_calls += 1
            try:
                result = fn(*args, **kwargs)
                stats.total_successes += 1
                stats.consecutive_failures = 0
                return result
            except Exception as exc:
                last_exc = exc
                stats.total_failures += 1
                stats.consecutive_failures += 1
                stats.last_failure_time = time.time()

                if stats.consecutive_failures >= self._circuit_break_threshold:
                    stats.circuit_open = True
                    raise CircuitOpenError(
                        f"Circuit opened for {fn_name!r} after "
                        f"{stats.consecutive_failures} consecutive failures"
                    ) from exc

                if attempt < self._max_retries:
                    delay = self._compute_delay(attempt)
                    self._sleep_fn(delay)

        raise last_exc  # type: ignore[misc]

    def reset_circuit(self, fn_name: str) -> None:
        """Reset the circuit breaker for a function."""
        if fn_name in self._stats:
            self._stats[fn_name].circuit_open = False
            self._stats[fn_name].consecutive_failures = 0

    def get_stats(self) -> Dict[str, dict]:
        """Return per-function stats."""
        result: dict[str, dict] = {}
        for name, s in self._stats.items():
            result[name] = {
                "total_calls": s.total_calls,
                "total_failures": s.total_failures,
                "total_successes": s.total_successes,
                "consecutive_failures": s.consecutive_failures,
                "circuit_open": s.circuit_open,
            }
        return result
