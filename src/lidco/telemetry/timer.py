"""Q129 — Metrics & Telemetry: Timer and TimerRegistry."""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator, Optional

from lidco.telemetry.metrics_store import MetricsStore


@dataclass
class TimingRecord:
    name: str
    elapsed: float
    started_at: float
    ended_at: float


class Timer:
    """Measures elapsed time and optionally records to a MetricsStore."""

    def __init__(self, name: str, store: Optional[MetricsStore] = None) -> None:
        self._name = name
        self._store = store
        self._started_at: Optional[float] = None

    @property
    def name(self) -> str:
        return self._name

    def start(self) -> None:
        self._started_at = time.time()

    def stop(self) -> TimingRecord:
        if self._started_at is None:
            raise RuntimeError("Timer was not started")
        ended_at = time.time()
        elapsed = ended_at - self._started_at
        record = TimingRecord(
            name=self._name,
            elapsed=elapsed,
            started_at=self._started_at,
            ended_at=ended_at,
        )
        if self._store is not None:
            self._store.record(self._name, elapsed)
        self._started_at = None
        return record

    @contextmanager
    def measure(self) -> Generator:
        self.start()
        try:
            yield self
        finally:
            self.stop()


class TimerRegistry:
    """Registry that manages a collection of named timers."""

    def __init__(self, store: Optional[MetricsStore] = None) -> None:
        self._store = store if store is not None else MetricsStore()
        self._timers: dict[str, Timer] = {}

    def get_or_create(self, name: str) -> Timer:
        if name not in self._timers:
            self._timers[name] = Timer(name, store=self._store)
        return self._timers[name]

    def record(self, name: str, elapsed: float) -> None:
        self._store.record(name, elapsed)

    def summary(self) -> dict:
        result: dict[str, float] = {}
        for name in self._store.names():
            result[name] = self._store.aggregate(name, fn="avg")
        return result
