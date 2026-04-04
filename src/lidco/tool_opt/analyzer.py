"""ToolUseAnalyzer — analyse tool-call patterns for efficiency."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CallRecord:
    """A single recorded tool call."""

    tool_name: str
    args: dict[str, Any]
    duration: float
    timestamp: float = field(default_factory=time.time)


class ToolUseAnalyzer:
    """Record and analyse tool-call history for optimisation hints."""

    def __init__(self) -> None:
        self._calls: list[CallRecord] = []

    # -- recording ----------------------------------------------------

    def record_call(
        self,
        tool_name: str,
        args: dict[str, Any] | None = None,
        duration: float = 0.0,
    ) -> CallRecord:
        """Record a tool call and return the record."""
        rec = CallRecord(
            tool_name=tool_name,
            args=args if args is not None else {},
            duration=duration,
        )
        self._calls.append(rec)
        return rec

    @property
    def calls(self) -> list[CallRecord]:
        return list(self._calls)

    # -- analysis -----------------------------------------------------

    def efficiency_score(self) -> float:
        """Return a 0-1 score (1 = perfectly efficient).

        Penalises unnecessary (duplicate consecutive same-tool+args) calls and
        rewards fast durations.
        """
        if not self._calls:
            return 1.0

        unnecessary = len(self.unnecessary_calls())
        total = len(self._calls)
        dup_ratio = unnecessary / total

        durations = [c.duration for c in self._calls]
        avg_dur = sum(durations) / len(durations) if durations else 0.0
        # speed component: if average < 0.5s treat as perfect; scale linearly up to 5s
        speed = max(0.0, 1.0 - min(avg_dur, 5.0) / 5.0)

        return round((1.0 - dup_ratio) * 0.6 + speed * 0.4, 4)

    def unnecessary_calls(self) -> list[CallRecord]:
        """Return calls that duplicate the immediately preceding call."""
        result: list[CallRecord] = []
        for i in range(1, len(self._calls)):
            prev = self._calls[i - 1]
            cur = self._calls[i]
            if cur.tool_name == prev.tool_name and cur.args == prev.args:
                result.append(cur)
        return result

    def missed_opportunities(self) -> list[str]:
        """Heuristic: suggest read-batching and parallelisation."""
        hints: list[str] = []
        read_targets: list[str] = []
        for c in self._calls:
            if c.tool_name in ("Read", "read", "file_read"):
                path = c.args.get("path") or c.args.get("file_path") or ""
                if path:
                    read_targets.append(path)
        if len(read_targets) > 2:
            hints.append(
                f"Consider batching {len(read_targets)} sequential reads into a single glob/multi-read."
            )

        # detect alternating edit-read pattern
        names = [c.tool_name for c in self._calls]
        for i in range(len(names) - 2):
            if names[i] in ("Edit", "edit") and names[i + 1] in ("Read", "read", "file_read") and names[i + 2] in ("Edit", "edit"):
                hints.append("Edit-Read-Edit pattern detected; pre-read the file once before editing.")
                break

        return hints

    def summary(self) -> dict[str, Any]:
        """Aggregate summary of recorded calls."""
        tool_counts: dict[str, int] = {}
        total_duration = 0.0
        for c in self._calls:
            tool_counts[c.tool_name] = tool_counts.get(c.tool_name, 0) + 1
            total_duration += c.duration

        return {
            "total_calls": len(self._calls),
            "tool_counts": dict(sorted(tool_counts.items())),
            "total_duration": round(total_duration, 4),
            "efficiency_score": self.efficiency_score(),
            "unnecessary_calls": len(self.unnecessary_calls()),
            "missed_opportunities": self.missed_opportunities(),
        }
