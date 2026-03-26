"""ObjectPool — reusable object pool with blocking acquire (stdlib only)."""
from __future__ import annotations

import contextlib
import threading
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class PoolExhausted(Exception):
    """Raised when no objects are available and max_size is reached."""


@dataclass
class PoolStats:
    total_created: int = 0
    total_acquired: int = 0
    total_released: int = 0
    pool_size: int = 0   # currently available
    in_use: int = 0      # acquired but not released


class ObjectPool(Generic[T]):
    """
    Thread-safe reusable object pool.

    Parameters
    ----------
    factory:
        Zero-argument callable that creates a new object.
    max_size:
        Maximum total objects (available + in-use combined).
    validate:
        Optional callable that returns *True* if an object is still usable.
        Objects failing validation are discarded on release.
    """

    def __init__(
        self,
        factory: Callable[[], T],
        max_size: int = 10,
        validate: Callable[[T], bool] | None = None,
    ) -> None:
        self._factory = factory
        self._max_size = max_size
        self._validate = validate

        self._pool: list[T] = []          # available objects (LIFO)
        self._in_use: set[int] = set()    # id() of acquired objects
        self._total_created = 0
        self._total_acquired = 0
        self._total_released = 0
        self._condition = threading.Condition()

    # ------------------------------------------------------------------ public

    def acquire(self, timeout: float | None = None) -> T:
        """
        Return an object from the pool, or create a new one.

        If *max_size* is reached and no objects are available, block up to
        *timeout* seconds.  Raises :exc:`PoolExhausted` if still unavailable.
        """
        with self._condition:
            while True:
                # Try to return a pooled object
                if self._pool:
                    obj = self._pool.pop()
                    self._in_use.add(id(obj))
                    self._total_acquired += 1
                    return obj

                # Can we create a new object?
                if self._total_created - self._total_released < self._max_size or len(self._in_use) < self._max_size:
                    total_live = len(self._pool) + len(self._in_use)
                    if total_live < self._max_size:
                        obj = self._factory()
                        self._total_created += 1
                        self._in_use.add(id(obj))
                        self._total_acquired += 1
                        return obj

                # Block or raise
                if timeout == 0 or (timeout is None and not self._pool and len(self._in_use) >= self._max_size):
                    raise PoolExhausted(
                        f"Pool exhausted (max_size={self._max_size})"
                    )
                notified = self._condition.wait(timeout=timeout)
                if not notified:
                    raise PoolExhausted(
                        f"Pool exhausted after {timeout}s timeout (max_size={self._max_size})"
                    )

    def release(self, obj: T) -> None:
        """Return *obj* to the pool (or discard if validation fails)."""
        with self._condition:
            oid = id(obj)
            if oid not in self._in_use:
                # Not tracked — silently ignore
                return
            self._in_use.discard(oid)
            self._total_released += 1

            if self._validate is None or self._validate(obj):
                self._pool.append(obj)
            # else: discard — total_live decreases, allowing future creates

            self._condition.notify()

    @contextlib.contextmanager
    def acquire_context(self, timeout: float | None = None):
        """Context manager that acquires and releases an object."""
        obj = self.acquire(timeout=timeout)
        try:
            yield obj
        finally:
            self.release(obj)

    def drain(self) -> int:
        """Clear all available (unreleased) objects.  Return count drained."""
        with self._condition:
            count = len(self._pool)
            self._pool.clear()
            return count

    def stats(self) -> PoolStats:
        with self._condition:
            return PoolStats(
                total_created=self._total_created,
                total_acquired=self._total_acquired,
                total_released=self._total_released,
                pool_size=len(self._pool),
                in_use=len(self._in_use),
            )

    @property
    def size(self) -> int:
        """Total objects: available + in-use."""
        with self._condition:
            return len(self._pool) + len(self._in_use)

    @property
    def pool_size(self) -> int:
        """Available objects."""
        with self._condition:
            return len(self._pool)
