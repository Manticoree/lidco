"""Q129 — Metrics & Telemetry: Counter and CounterRegistry."""
from __future__ import annotations

from typing import Optional


class Counter:
    """A named, thread-friendly numeric counter."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._value: float = 0.0

    @property
    def name(self) -> str:
        return self._name

    @property
    def value(self) -> float:
        return self._value

    def increment(self, by: float = 1.0) -> float:
        self._value += by
        return self._value

    def decrement(self, by: float = 1.0) -> float:
        self._value -= by
        return self._value

    def reset(self) -> None:
        self._value = 0.0


class CounterRegistry:
    """Registry that manages a collection of named counters."""

    def __init__(self) -> None:
        self._counters: dict[str, Counter] = {}

    def get_or_create(self, name: str) -> Counter:
        if name not in self._counters:
            self._counters[name] = Counter(name)
        return self._counters[name]

    def get(self, name: str) -> Optional[Counter]:
        return self._counters.get(name)

    def all_values(self) -> dict[str, float]:
        return {name: c.value for name, c in self._counters.items()}

    def reset_all(self) -> None:
        for c in self._counters.values():
            c.reset()

    def names(self) -> list[str]:
        return list(self._counters.keys())
