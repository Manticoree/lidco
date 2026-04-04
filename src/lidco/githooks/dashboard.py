"""HookDashboard — execution metrics and trend reporting.

Records hook execution results and computes pass rates, average durations,
failure rankings, and per-hook trend data.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class _Record:
    hook: str
    passed: bool
    duration: float
    timestamp: float


class HookDashboard:
    """Track and report on hook execution metrics."""

    def __init__(self) -> None:
        self._records: List[_Record] = []

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_execution(self, hook: str, passed: bool, duration: float) -> None:
        """Record one execution of *hook*."""
        self._records.append(
            _Record(hook=hook, passed=passed, duration=duration, timestamp=time.time())
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def pass_rate(self, hook: str) -> float:
        """Return pass rate [0.0 .. 1.0] for *hook*. Returns 0.0 if no data."""
        relevant = [r for r in self._records if r.hook == hook]
        if not relevant:
            return 0.0
        return sum(1 for r in relevant if r.passed) / len(relevant)

    def avg_duration(self, hook: str) -> float:
        """Return average duration in seconds. Returns 0.0 if no data."""
        relevant = [r for r in self._records if r.hook == hook]
        if not relevant:
            return 0.0
        return sum(r.duration for r in relevant) / len(relevant)

    def most_failed(self, top_n: int = 5) -> List[dict]:
        """Return the *top_n* hooks with the highest failure count.

        Each entry: {"hook": str, "failures": int, "total": int}.
        """
        counts: Dict[str, Dict[str, int]] = {}
        for r in self._records:
            bucket = counts.setdefault(r.hook, {"failures": 0, "total": 0})
            bucket["total"] += 1
            if not r.passed:
                bucket["failures"] += 1
        ranked = sorted(counts.items(), key=lambda kv: kv[1]["failures"], reverse=True)
        return [
            {"hook": name, "failures": data["failures"], "total": data["total"]}
            for name, data in ranked[:top_n]
        ]

    def trends(self, hook: str) -> List[dict]:
        """Return per-execution trend data for *hook*.

        Each entry: {"timestamp": float, "passed": bool, "duration": float}.
        """
        return [
            {"timestamp": r.timestamp, "passed": r.passed, "duration": r.duration}
            for r in self._records
            if r.hook == hook
        ]

    def summary(self) -> dict:
        """High-level dashboard summary."""
        hooks = sorted({r.hook for r in self._records})
        total_runs = len(self._records)
        total_pass = sum(1 for r in self._records if r.passed)
        return {
            "total_runs": total_runs,
            "total_pass": total_pass,
            "total_fail": total_runs - total_pass,
            "overall_pass_rate": (total_pass / total_runs) if total_runs else 0.0,
            "hooks_tracked": hooks,
        }
