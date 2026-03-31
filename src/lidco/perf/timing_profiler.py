"""TimingProfiler — measure execution time of operations."""
from __future__ import annotations

import functools
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator


@dataclass
class TimingRecord:
    """A single timing measurement."""

    name: str
    elapsed: float
    started_at: float
    ended_at: float
    metadata: dict[str, Any] = field(default_factory=dict)


class TimingProfiler:
    """Tracks timing of named operations."""

    def __init__(self) -> None:
        self._active: dict[str, tuple[str, float]] = {}  # timing_id -> (name, start)
        self._records: list[TimingRecord] = []

    def start(self, name: str) -> str:
        """Start a named timing. Returns a timing_id."""
        timing_id = uuid.uuid4().hex[:12]
        self._active[timing_id] = (name, time.monotonic())
        return timing_id

    def stop(self, timing_id: str) -> TimingRecord:
        """Stop a timing by id and return the record."""
        if timing_id not in self._active:
            raise KeyError(f"Unknown timing_id: {timing_id}")
        name, started = self._active.pop(timing_id)
        ended = time.monotonic()
        record = TimingRecord(
            name=name,
            elapsed=ended - started,
            started_at=started,
            ended_at=ended,
        )
        self._records.append(record)
        return record

    @contextmanager
    def measure(self, name: str) -> Iterator[None]:
        """Context manager that records timing for the block."""
        tid = self.start(name)
        try:
            yield
        finally:
            self.stop(tid)

    def decorator(self, name: str | None = None) -> Callable:
        """Return a decorator that times the wrapped function."""
        def wrapper(fn: Callable) -> Callable:
            label = name or fn.__name__

            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                with self.measure(label):
                    return fn(*args, **kwargs)

            return sync_wrapper
        return wrapper

    @property
    def records(self) -> list[TimingRecord]:
        """All completed timing records."""
        return list(self._records)

    def summary(self) -> dict[str, dict[str, float]]:
        """Per-name statistics: avg, min, max, count."""
        groups: dict[str, list[float]] = {}
        for r in self._records:
            groups.setdefault(r.name, []).append(r.elapsed)
        result: dict[str, dict[str, float]] = {}
        for nm, times in groups.items():
            result[nm] = {
                "count": float(len(times)),
                "avg": sum(times) / len(times),
                "min": min(times),
                "max": max(times),
                "total": sum(times),
            }
        return result

    def slowest(self, n: int = 5) -> list[TimingRecord]:
        """Return the *n* slowest records."""
        return sorted(self._records, key=lambda r: r.elapsed, reverse=True)[:n]

    def clear(self) -> None:
        """Remove all records and active timings."""
        self._records.clear()
        self._active.clear()
