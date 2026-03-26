"""CircuitBreaker — CLOSED/OPEN/HALF_OPEN state machine (stdlib only)."""
from __future__ import annotations

import enum
import threading
import time
from dataclasses import dataclass


class CircuitState(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is attempted on an OPEN circuit."""

    def __init__(self, retry_after: float = 0.0) -> None:
        super().__init__(f"Circuit is OPEN. Retry after {retry_after:.1f}s")
        self.retry_after = retry_after


@dataclass
class CircuitStats:
    state: CircuitState
    failure_count: int
    success_count: int
    last_failure_time: float | None
    total_calls: int
    total_failures: int


class CircuitBreaker:
    """
    Circuit breaker: CLOSED → (failures ≥ threshold) → OPEN → (timeout elapsed) →
    HALF_OPEN → (success) → CLOSED | (failure) → OPEN.

    Parameters
    ----------
    failure_threshold:
        Consecutive failures required to open circuit.
    recovery_timeout:
        Seconds to wait in OPEN before attempting HALF_OPEN.
    half_open_max_calls:
        Number of test calls allowed in HALF_OPEN.
    excluded_exceptions:
        Exception types that do NOT count as failures.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1,
        excluded_exceptions: tuple[type[Exception], ...] = (),
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls
        self._excluded = excluded_exceptions

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: float | None = None
        self._total_calls = 0
        self._total_failures = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def last_failure_time(self) -> float | None:
        return self._last_failure_time

    def call(self, fn, *args, **kwargs):
        """
        Execute *fn*.  Tracks successes/failures and transitions state accordingly.

        Raises
        ------
        CircuitOpenError
            If state is OPEN and recovery timeout has not elapsed.
        """
        with self._lock:
            state = self._state
            now = time.monotonic()

            if state == CircuitState.OPEN:
                elapsed = now - (self._last_failure_time or 0)
                if elapsed >= self._recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                else:
                    raise CircuitOpenError(retry_after=self._recovery_timeout - elapsed)

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self._half_open_max_calls:
                    raise CircuitOpenError(retry_after=0.0)
                self._half_open_calls += 1

            self._total_calls += 1

        # Execute outside lock to avoid blocking other threads during fn call
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            if self._excluded and isinstance(exc, self._excluded):
                raise
            with self._lock:
                self._total_failures += 1
                self._failure_count += 1
                self._last_failure_time = time.monotonic()
                if self._state == CircuitState.HALF_OPEN:
                    self._state = CircuitState.OPEN
                    self._half_open_calls = 0
                elif self._failure_count >= self._failure_threshold:
                    self._state = CircuitState.OPEN
            raise

        with self._lock:
            self._failure_count = 0
            self._success_count += 1
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._half_open_calls = 0

        return result

    def reset(self) -> None:
        """Force state to CLOSED and zero all counters."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._last_failure_time = None

    def stats(self) -> CircuitStats:
        with self._lock:
            return CircuitStats(
                state=self._state,
                failure_count=self._failure_count,
                success_count=self._success_count,
                last_failure_time=self._last_failure_time,
                total_calls=self._total_calls,
                total_failures=self._total_failures,
            )
