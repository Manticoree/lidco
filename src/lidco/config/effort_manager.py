"""EffortManager — manage effort levels and token budgets.

Task 729: Q119.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional


class EffortLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    AUTO = "auto"


@dataclass
class EffortBudget:
    max_tokens: int
    thinking_tokens: int
    temperature: float


EFFORT_BUDGETS: dict[EffortLevel, EffortBudget] = {
    EffortLevel.LOW: EffortBudget(max_tokens=2048, thinking_tokens=512, temperature=0.3),
    EffortLevel.MEDIUM: EffortBudget(max_tokens=8192, thinking_tokens=2048, temperature=0.7),
    EffortLevel.HIGH: EffortBudget(max_tokens=32000, thinking_tokens=8000, temperature=1.0),
}


class EffortManager:
    """Persist and retrieve effort level settings."""

    def __init__(
        self,
        store_path: str = "/tmp/effort.json",
        write_fn: Optional[Callable[[str, str], None]] = None,
        read_fn: Optional[Callable[[str], str]] = None,
    ) -> None:
        self._store_path = store_path
        self._write_fn = write_fn or self._default_write
        self._read_fn = read_fn or self._default_read
        self._level: EffortLevel = EffortLevel.MEDIUM

    @property
    def level(self) -> EffortLevel:
        return self._level

    def set_level(self, level: "str | EffortLevel") -> EffortBudget:
        """Set effort level, persist, return the corresponding budget."""
        if isinstance(level, str):
            level = EffortLevel(level.lower())
        self._level = level
        self._persist()
        return self.get_budget()

    def get_budget(self, level: Optional[EffortLevel] = None) -> EffortBudget:
        """Return budget for *level* (or current level if None)."""
        target = level if level is not None else self._level
        if target == EffortLevel.AUTO:
            target = EffortLevel.MEDIUM
        return EFFORT_BUDGETS[target]

    def auto_select(self, word_count: int) -> EffortLevel:
        """Choose level based on prompt word count."""
        if word_count <= 5:
            return EffortLevel.LOW
        if word_count <= 50:
            return EffortLevel.MEDIUM
        return EffortLevel.HIGH

    def load(self) -> None:
        """Load persisted level from store; silently ignore errors."""
        try:
            raw = self._read_fn(self._store_path)
            data = json.loads(raw)
            self._level = EffortLevel(data["level"])
        except Exception:
            self._level = EffortLevel.MEDIUM

    # ------------------------------------------------------------------ #
    # Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _persist(self) -> None:
        data = json.dumps({"level": self._level.value})
        self._write_fn(self._store_path, data)

    @staticmethod
    def _default_write(path: str, data: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(data)

    @staticmethod
    def _default_read(path: str) -> str:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
