"""Context usage dashboard with breakdown and trends."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TurnUsage:
    """Immutable record of token usage at a given turn."""

    turn: int
    used: int
    delta: int = 0
    role_breakdown: tuple[tuple[str, int], ...] = ()


class UsageDashboard:
    """Tracks per-turn usage and renders an ASCII dashboard."""

    def __init__(self) -> None:
        self._turns: list[TurnUsage] = []
        self._peak_turn: int = 0
        self._peak_tokens: int = 0

    def record_turn(
        self,
        turn: int,
        used: int,
        breakdown: dict[str, int] | None = None,
    ) -> TurnUsage:
        """Record usage for *turn* and return the entry."""
        delta = used - self._turns[-1].used if self._turns else 0
        rb = tuple(sorted(breakdown.items())) if breakdown else ()
        entry = TurnUsage(turn=turn, used=used, delta=delta, role_breakdown=rb)
        self._turns = [*self._turns, entry]
        if used > self._peak_tokens:
            self._peak_tokens = used
            self._peak_turn = turn
        return entry

    def get_trend(self, last_n: int = 10) -> list[TurnUsage]:
        """Return the last *last_n* turn entries."""
        return list(self._turns[-last_n:])

    def average_per_turn(self) -> float:
        """Average tokens used per turn."""
        if not self._turns:
            return 0.0
        return sum(t.used for t in self._turns) / len(self._turns)

    def peak(self) -> TurnUsage | None:
        """Return the turn with highest usage."""
        if not self._turns:
            return None
        return max(self._turns, key=lambda t: t.used)

    def burn_rate(self) -> float:
        """Average token delta per turn."""
        if len(self._turns) < 2:
            return 0.0
        deltas = [t.delta for t in self._turns[1:]]
        return sum(deltas) / len(deltas) if deltas else 0.0

    def format_bar(self, used: int, total: int, width: int = 40) -> str:
        """Render ASCII progress bar."""
        if total <= 0:
            ratio = 0.0
        else:
            ratio = min(1.0, used / total)
        filled = int(ratio * width)
        empty = width - filled
        pct = ratio * 100.0
        return f"[{'█' * filled}{'░' * empty}] {pct:.1f}%"

    def summary(self, context_limit: int = 128000) -> str:
        """Multi-line dashboard summary."""
        lines: list[str] = ["Usage Dashboard:"]
        if not self._turns:
            lines.append("  No data recorded.")
            return "\n".join(lines)
        latest = self._turns[-1]
        lines.append(f"  {self.format_bar(latest.used, context_limit)}")
        lines.append(f"  Tokens: {latest.used:,} / {context_limit:,}")
        lines.append(f"  Turns: {len(self._turns)}")
        lines.append(f"  Avg/turn: {self.average_per_turn():,.0f}")
        lines.append(f"  Burn rate: {self.burn_rate():,.0f} tokens/turn")
        pk = self.peak()
        if pk is not None:
            lines.append(f"  Peak: {pk.used:,} at turn {pk.turn}")
        return "\n".join(lines)
