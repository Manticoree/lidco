"""Team analytics — usage tracking and reporting."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class UsageRecord:
    """A single usage event."""

    user_id: str
    action: str
    cost: float = 0.0
    tokens: int = 0
    timestamp: float = 0.0


class TeamAnalytics:
    """Collects and queries team usage analytics."""

    def __init__(self, team_id: str) -> None:
        self.team_id = team_id
        self._records: list[UsageRecord] = []

    def record(self, user_id: str, action: str, cost: float = 0.0, tokens: int = 0) -> None:
        """Record a usage event."""
        self._records.append(
            UsageRecord(
                user_id=user_id,
                action=action,
                cost=cost,
                tokens=tokens,
                timestamp=time.time(),
            )
        )

    def per_member_cost(self) -> dict[str, float]:
        """Return total cost per member."""
        result: dict[str, float] = defaultdict(float)
        for r in self._records:
            result[r.user_id] += r.cost
        return dict(result)

    def per_member_tokens(self) -> dict[str, int]:
        """Return total tokens per member."""
        result: dict[str, int] = defaultdict(int)
        for r in self._records:
            result[r.user_id] += r.tokens
        return dict(result)

    def total_cost(self) -> float:
        """Return sum of all costs."""
        return sum(r.cost for r in self._records)

    def total_tokens(self) -> int:
        """Return sum of all tokens."""
        return sum(r.tokens for r in self._records)

    def activity_timeline(self, last_n: int = 100) -> list[UsageRecord]:
        """Return the last *last_n* records."""
        return self._records[-last_n:]

    def top_contributors(self, n: int = 5) -> list[tuple[str, int]]:
        """Return top *n* contributors by number of actions."""
        counts: dict[str, int] = defaultdict(int)
        for r in self._records:
            counts[r.user_id] += 1
        sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_items[:n]

    def summary(self) -> str:
        """Return a human-readable summary."""
        lines = [
            f"Team: {self.team_id}",
            f"Total records: {len(self._records)}",
            f"Total cost: ${self.total_cost():.4f}",
            f"Total tokens: {self.total_tokens()}",
        ]
        top = self.top_contributors(3)
        if top:
            lines.append("Top contributors:")
            for user_id, count in top:
                lines.append(f"  {user_id}: {count} action(s)")
        return "\n".join(lines)
