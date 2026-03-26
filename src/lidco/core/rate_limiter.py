"""RateLimiter — token bucket algorithm, thread-safe (stdlib only)."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class RateLimiterStats:
    total_acquired: int
    total_rejected: int
    available_tokens: float


class RateLimiter:
    """
    Token bucket rate limiter.

    Parameters
    ----------
    rate:
        Token refill rate (tokens per second).
    capacity:
        Maximum bucket capacity.
    """

    def __init__(self, rate: float, capacity: float) -> None:
        if rate <= 0:
            raise ValueError(f"rate must be > 0, got {rate}")
        if capacity <= 0:
            raise ValueError(f"capacity must be > 0, got {capacity}")
        self._rate = rate
        self._capacity = capacity
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()
        self._total_acquired = 0
        self._total_rejected = 0

    @property
    def capacity(self) -> float:
        return self._capacity

    @property
    def rate(self) -> float:
        return self._rate

    @property
    def available_tokens(self) -> float:
        with self._lock:
            self._refill()
            return self._tokens

    def _refill(self) -> None:
        """Add tokens based on elapsed time. Must be called under lock."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        added = elapsed * self._rate
        self._tokens = min(self._capacity, self._tokens + added)
        self._last_refill = now

    def acquire(self, tokens: float = 1) -> bool:
        """Non-blocking acquire. Return True if tokens available, False otherwise."""
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                self._total_acquired += 1
                return True
            self._total_rejected += 1
            return False

    def acquire_wait(self, tokens: float = 1, timeout: float | None = None) -> bool:
        """
        Blocking acquire.  Polls every 10 ms up to *timeout* seconds.
        Return True if acquired, False if timed out.
        """
        deadline = (time.monotonic() + timeout) if timeout is not None else None
        while True:
            if self.acquire(tokens):
                return True
            if deadline is not None and time.monotonic() >= deadline:
                return False
            time.sleep(0.01)

    def reset(self) -> None:
        """Restore bucket to full capacity."""
        with self._lock:
            self._tokens = self._capacity
            self._last_refill = time.monotonic()

    def stats(self) -> RateLimiterStats:
        return RateLimiterStats(
            total_acquired=self._total_acquired,
            total_rejected=self._total_rejected,
            available_tokens=self.available_tokens,
        )


class RateLimiterGroup:
    """Manage a collection of named rate limiters."""

    def __init__(self) -> None:
        self._limiters: dict[str, RateLimiter] = {}
        self._lock = threading.Lock()

    def add(self, name: str, rate: float, capacity: float) -> RateLimiter:
        """Create and register a named limiter. Return it."""
        limiter = RateLimiter(rate, capacity)
        with self._lock:
            self._limiters = {**self._limiters, name: limiter}
        return limiter

    def get(self, name: str) -> RateLimiter | None:
        with self._lock:
            return self._limiters.get(name)

    def remove(self, name: str) -> bool:
        with self._lock:
            if name not in self._limiters:
                return False
            self._limiters = {k: v for k, v in self._limiters.items() if k != name}
            return True

    def acquire(self, name: str, tokens: float = 1) -> bool:
        """Acquire from named limiter. Raises KeyError if not found."""
        limiter = self.get(name)
        if limiter is None:
            raise KeyError(f"No limiter named {name!r}")
        return limiter.acquire(tokens)

    def list_limiters(self) -> list[str]:
        with self._lock:
            return sorted(self._limiters.keys())
