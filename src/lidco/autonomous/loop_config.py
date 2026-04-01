"""Loop configuration, state, and iteration result types (task 1052)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LoopState(str, Enum):
    """Lifecycle state of an autonomous loop."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class LoopConfig:
    """Immutable configuration for an autonomous loop run."""

    prompt: str
    max_iterations: int = 10
    completion_promise: str | None = None
    timeout_s: float | None = None
    cooldown_s: float = 1.0
    allow_early_exit: bool = False


@dataclass(frozen=True)
class IterationResult:
    """Immutable record of a single loop iteration."""

    iteration: int
    output: str
    duration_ms: int
    claimed_complete: bool


__all__ = [
    "IterationResult",
    "LoopConfig",
    "LoopState",
]
