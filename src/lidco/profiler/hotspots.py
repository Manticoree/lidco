"""HotspotFinder — find performance hotspots; rank by time/calls; suggest optimizations."""
from __future__ import annotations

from dataclasses import dataclass

from lidco.profiler.runner import ProfileResult


@dataclass(frozen=True)
class Hotspot:
    """A single performance hotspot."""

    function_name: str
    file_path: str
    time_ms: float
    call_count: int
    percentage: float
    suggestion: str = ""


class HotspotFinder:
    """Find performance hotspots; rank by time/calls; suggest optimizations."""

    def __init__(self) -> None:
        self._suggestion_rules: dict[str, str] = {
            "loop": "Consider vectorising or reducing loop iterations.",
            "sort": "Use a more efficient sorting algorithm or pre-sorted data.",
            "open": "Batch file operations or use buffered I/O.",
            "sleep": "Remove or reduce sleep duration.",
            "import": "Use lazy imports to reduce startup time.",
            "print": "Remove debug print statements in hot paths.",
        }

    # ------------------------------------------------------------------
    # Finding hotspots
    # ------------------------------------------------------------------

    def find(self, result: ProfileResult, limit: int = 10) -> list[Hotspot]:
        """Top functions by time."""
        if not result.entries:
            return []
        total = result.total_time or 1.0
        sorted_entries = sorted(
            result.entries, key=lambda e: e.get("time_ms", 0.0), reverse=True
        )
        hotspots: list[Hotspot] = []
        for entry in sorted_entries[:limit]:
            t = entry.get("time_ms", 0.0)
            hs = Hotspot(
                function_name=entry.get("code", "unknown"),
                file_path=f"line:{entry.get('line', 0)}",
                time_ms=t,
                call_count=entry.get("calls", 0),
                percentage=round((t / total) * 100, 2),
            )
            hotspots.append(hs)
        return hotspots

    def by_calls(self, result: ProfileResult, limit: int = 10) -> list[Hotspot]:
        """Top functions by call count."""
        if not result.entries:
            return []
        total = result.total_time or 1.0
        sorted_entries = sorted(
            result.entries, key=lambda e: e.get("calls", 0), reverse=True
        )
        hotspots: list[Hotspot] = []
        for entry in sorted_entries[:limit]:
            t = entry.get("time_ms", 0.0)
            hs = Hotspot(
                function_name=entry.get("code", "unknown"),
                file_path=f"line:{entry.get('line', 0)}",
                time_ms=t,
                call_count=entry.get("calls", 0),
                percentage=round((t / total) * 100, 2),
            )
            hotspots.append(hs)
        return hotspots

    def suggest_optimization(self, hotspot: Hotspot) -> str:
        """Heuristic suggestion for a hotspot."""
        name_lower = hotspot.function_name.lower()
        for keyword, suggestion in self._suggestion_rules.items():
            if keyword in name_lower:
                return suggestion
        if hotspot.call_count > 100:
            return "High call count — consider caching or memoization."
        if hotspot.percentage > 50:
            return "Dominates execution — profile sub-calls for further optimisation."
        return "No specific suggestion — review algorithm complexity."

    def compare_hotspots(
        self, before: list[Hotspot], after: list[Hotspot]
    ) -> list[dict]:
        """Compare hotspots before/after optimisation."""
        before_map = {h.function_name: h for h in before}
        after_map = {h.function_name: h for h in after}
        all_names = list(dict.fromkeys(
            [h.function_name for h in before] + [h.function_name for h in after]
        ))
        results: list[dict] = []
        for name in all_names:
            b = before_map.get(name)
            a = after_map.get(name)
            if b and a:
                diff = a.time_ms - b.time_ms
                status = "improved" if diff < 0 else ("regressed" if diff > 0 else "unchanged")
            elif b and not a:
                diff = -b.time_ms
                status = "removed"
            else:
                diff = a.time_ms if a else 0.0
                status = "new"
            results.append({
                "function": name,
                "time_diff": round(diff, 4),
                "status": status,
            })
        return results

    def summary(self, result: ProfileResult) -> dict:
        """Summary for a profile result."""
        hotspots = self.find(result, limit=5)
        return {
            "total_hotspots": len(result.entries),
            "top5": [h.function_name for h in hotspots],
            "total_time": result.total_time,
        }
