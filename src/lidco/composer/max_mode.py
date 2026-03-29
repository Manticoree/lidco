"""MaxModeManager — normal/max/mini mode switching with budget and usage tracking (stdlib only)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MaxMode(Enum):
    NORMAL = "normal"
    MAX = "max"
    MINI = "mini"


@dataclass
class ModeConfig:
    mode: MaxMode
    base_budget: int
    max_tool_calls: int
    extended_timeout: bool


MODE_CONFIGS: dict[MaxMode, ModeConfig] = {
    MaxMode.NORMAL: ModeConfig(MaxMode.NORMAL, 32_000, 25, False),
    MaxMode.MAX: ModeConfig(MaxMode.MAX, 200_000, 200, True),
    MaxMode.MINI: ModeConfig(MaxMode.MINI, 8_000, 10, False),
}


@dataclass
class UsageSummary:
    current_mode: str
    tokens_used: int
    tool_calls_made: int
    mode_history: list[dict] = field(default_factory=list)


class MaxModeManager:
    """Manages normal/max/mini mode transitions and usage tracking."""

    def __init__(
        self,
        adaptive_budget: Any = None,
        composer_session: Any = None,
    ) -> None:
        self._adaptive_budget = adaptive_budget
        self._composer_session = composer_session
        self._mode: MaxMode = MaxMode.NORMAL
        self._tokens_used: int = 0
        self._tool_calls_made: int = 0
        self._mode_history: list[dict] = []

    @property
    def active_mode(self) -> MaxMode:
        return self._mode

    @property
    def config(self) -> ModeConfig:
        return MODE_CONFIGS[self._mode]

    def activate(self, mode: str | MaxMode) -> ModeConfig:
        """Switch to a new mode. Accepts string or MaxMode enum."""
        if isinstance(mode, str):
            mode = MaxMode(mode)

        old_mode = self._mode
        self._mode = mode
        cfg = MODE_CONFIGS[mode]

        # Update adaptive budget if available
        if self._adaptive_budget is not None and hasattr(self._adaptive_budget, "base_budget"):
            self._adaptive_budget.base_budget = cfg.base_budget

        # Update composer session if available
        if self._composer_session is not None and hasattr(self._composer_session, "max_tool_calls"):
            self._composer_session.max_tool_calls = cfg.max_tool_calls

        import time as _time

        self._mode_history = [
            *self._mode_history,
            {"from": old_mode.value, "to": mode.value, "mode": mode.value, "timestamp": _time.time()},
        ]

        return cfg

    def record_usage(self, tokens: int, tool_calls: int = 0) -> None:
        """Record token and tool-call usage."""
        self._tokens_used = self._tokens_used + tokens
        self._tool_calls_made = self._tool_calls_made + tool_calls

    def usage_summary(self) -> UsageSummary:
        """Return a snapshot of current usage."""
        return UsageSummary(
            current_mode=self._mode.value,
            tokens_used=self._tokens_used,
            tool_calls_made=self._tool_calls_made,
            mode_history=list(self._mode_history),
        )

    def reset_usage(self) -> None:
        """Reset usage counters to zero."""
        self._tokens_used = 0
        self._tool_calls_made = 0
