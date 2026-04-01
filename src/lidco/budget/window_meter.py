"""Real-time context window utilization tracking."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TokenAccount:
    """Token usage for a single role."""

    role: str
    tokens: int = 0
    message_count: int = 0


@dataclass(frozen=True)
class WindowSnapshot:
    """Immutable snapshot of context window state."""

    used: int = 0
    limit: int = 128000
    accounts: tuple[TokenAccount, ...] = ()
    timestamp: float = field(default_factory=time.time)
    turn: int = 0


class ContextWindowMeter:
    """Tracks real-time context window utilization by role."""

    def __init__(self, context_limit: int = 128000) -> None:
        self._limit = context_limit
        self._accounts: dict[str, int] = {}
        self._msg_counts: dict[str, int] = {}
        self._history: list[WindowSnapshot] = []
        self._turn: int = 0
        self._peak: int = 0

    def record(self, role: str, tokens: int) -> None:
        """Add *tokens* for *role*. Increments turn on 'user' role."""
        self._accounts = {
            **self._accounts,
            role: self._accounts.get(role, 0) + tokens,
        }
        self._msg_counts = {
            **self._msg_counts,
            role: self._msg_counts.get(role, 0) + 1,
        }
        if role == "user":
            self._turn += 1
        current = self.used
        if current > self._peak:
            self._peak = current
        self._history = [*self._history, self.snapshot()]

    def remove(self, role: str, tokens: int) -> None:
        """Subtract *tokens* for *role* (floor at 0)."""
        current = self._accounts.get(role, 0)
        self._accounts = {
            **self._accounts,
            role: max(0, current - tokens),
        }

    @property
    def used(self) -> int:
        """Total tokens across all roles."""
        return sum(self._accounts.values())

    @property
    def remaining(self) -> int:
        """Tokens left before hitting limit."""
        return max(0, self._limit - self.used)

    def utilization(self) -> float:
        """Utilization ratio 0.0-1.0."""
        if self._limit <= 0:
            return 0.0
        return min(1.0, self.used / self._limit)

    def percentage(self) -> float:
        """Utilization as percentage 0.0-100.0."""
        return self.utilization() * 100.0

    def snapshot(self) -> WindowSnapshot:
        """Capture current state as immutable snapshot."""
        accounts = tuple(
            TokenAccount(role=r, tokens=t, message_count=self._msg_counts.get(r, 0))
            for r, t in sorted(self._accounts.items())
        )
        return WindowSnapshot(
            used=self.used,
            limit=self._limit,
            accounts=accounts,
            turn=self._turn,
        )

    def get_breakdown(self) -> dict[str, int]:
        """Return role-to-token mapping."""
        return dict(self._accounts)

    def peak_usage(self) -> int:
        """Highest usage point observed."""
        return self._peak

    def reset(self) -> None:
        """Clear all tracking state."""
        self._accounts = {}
        self._msg_counts = {}
        self._history = []
        self._turn = 0
        self._peak = 0

    def summary(self) -> str:
        """Formatted one-line summary."""
        parts = [f"Context: {self.used:,} / {self._limit:,} ({self.percentage():.1f}%)"]
        for role in sorted(self._accounts):
            parts.append(f"{role}: {self._accounts[role]:,}")
        return " | ".join(parts)
