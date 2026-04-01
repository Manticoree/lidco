"""Analyze profiling data and produce reports."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProfileEntry:
    """A single profiling entry for a function."""

    function: str
    file: str = ""
    calls: int = 0
    total_time: float = 0.0
    cumulative_time: float = 0.0
    per_call: float = 0.0


@dataclass(frozen=True)
class ProfileReport:
    """Aggregated profiling report."""

    entries: tuple[ProfileEntry, ...] = ()
    total_time: float = 0.0
    entry_count: int = 0


class ProfileAnalyzer:
    """Collect profile entries and produce reports."""

    def __init__(self) -> None:
        self._entries: list[ProfileEntry] = []

    def add_entry(self, entry: ProfileEntry) -> None:
        """Add a profiling entry."""
        self._entries.append(entry)

    def top_functions(self, n: int = 10) -> list[ProfileEntry]:
        """Return top *n* functions by cumulative_time descending."""
        return sorted(
            self._entries, key=lambda e: e.cumulative_time, reverse=True
        )[:n]

    def hot_paths(self) -> list[ProfileEntry]:
        """Return entries where per_call exceeds the average per_call."""
        if not self._entries:
            return []
        avg = sum(e.per_call for e in self._entries) / len(self._entries)
        return [e for e in self._entries if e.per_call > avg]

    def compare(
        self, report1: ProfileReport, report2: ProfileReport
    ) -> dict[str, tuple[float, float]]:
        """Compare two reports, returning {function: (time1, time2)}."""
        times1: dict[str, float] = {
            e.function: e.cumulative_time for e in report1.entries
        }
        times2: dict[str, float] = {
            e.function: e.cumulative_time for e in report2.entries
        }
        all_funcs = set(times1) | set(times2)
        return {f: (times1.get(f, 0.0), times2.get(f, 0.0)) for f in all_funcs}

    def report(self) -> ProfileReport:
        """Build a :class:`ProfileReport` from collected entries."""
        total = sum(e.total_time for e in self._entries)
        return ProfileReport(
            entries=tuple(self._entries),
            total_time=total,
            entry_count=len(self._entries),
        )

    def summary(self) -> str:
        """Human-readable summary string."""
        r = self.report()
        lines = [f"Profile: {r.entry_count} entries, total {r.total_time:.4f}s"]
        for e in self.top_functions(5):
            lines.append(
                f"  {e.function}: {e.cumulative_time:.4f}s "
                f"({e.calls} calls)"
            )
        return "\n".join(lines)
