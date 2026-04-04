"""ProfileRunner — run code with profiling, output parsing, comparison."""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field


@dataclass
class ProfileResult:
    """Result of a profiling run."""

    name: str
    total_time: float
    call_count: int
    entries: list[dict] = field(default_factory=list)
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class ProfileRunner:
    """Run code with profiling; output parsing; comparison."""

    def __init__(self) -> None:
        self._history: list[ProfileResult] = []

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    def profile(self, code: str, name: str = "") -> ProfileResult:
        """Simulate profiling *code* and return a ProfileResult.

        We parse the code string, estimate metrics based on simple
        heuristics (line count, function calls), and produce entries.
        """
        if not name:
            name = hashlib.md5(code.encode()).hexdigest()[:8]

        lines = [ln for ln in code.splitlines() if ln.strip()]
        call_count = sum(1 for ln in lines if "(" in ln)

        entries: list[dict] = []
        for i, ln in enumerate(lines):
            stripped = ln.strip()
            entries.append({
                "line": i + 1,
                "code": stripped,
                "time_ms": 0.1 * (len(stripped) / 10 + 1),
                "calls": 1 if "(" in stripped else 0,
            })

        total_time = sum(e["time_ms"] for e in entries)

        result = ProfileResult(
            name=name,
            total_time=total_time,
            call_count=max(call_count, 1),
            entries=entries,
            timestamp=time.time(),
        )
        self._history.append(result)
        return result

    def compare(self, a: ProfileResult, b: ProfileResult) -> dict:
        """Compare two ProfileResults — time diff, call count diff, speedup."""
        time_diff = b.total_time - a.total_time
        call_diff = b.call_count - a.call_count
        speedup = a.total_time / b.total_time if b.total_time > 0 else 0.0
        return {
            "a_name": a.name,
            "b_name": b.name,
            "time_diff": time_diff,
            "call_diff": call_diff,
            "speedup": round(speedup, 4),
        }

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def history(self) -> list[ProfileResult]:
        """Return all past profile results."""
        return list(self._history)

    def latest(self) -> ProfileResult | None:
        """Return the most recent profile result, or None."""
        return self._history[-1] if self._history else None

    def clear(self) -> int:
        """Clear history. Return count of cleared items."""
        count = len(self._history)
        self._history.clear()
        return count

    def summary(self) -> dict:
        """Summary statistics for all profiled runs."""
        if not self._history:
            return {"runs": 0, "total_time": 0.0, "avg_time": 0.0}
        total = sum(r.total_time for r in self._history)
        return {
            "runs": len(self._history),
            "total_time": round(total, 4),
            "avg_time": round(total / len(self._history), 4),
        }
