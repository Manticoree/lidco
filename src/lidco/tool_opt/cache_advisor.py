"""ToolCacheAdvisor — detect repeated calls and suggest caching."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CachedCall:
    """A recorded call with its result for cache analysis."""

    tool: str
    args: dict[str, Any]
    result: Any
    count: int = 1


class ToolCacheAdvisor:
    """Record tool calls + results, detect repetition and suggest caching."""

    def __init__(self) -> None:
        self._calls: list[tuple[str, dict[str, Any], Any]] = []

    # -- recording ----------------------------------------------------

    def record_call(
        self,
        tool: str,
        args: dict[str, Any] | None = None,
        result: Any = None,
    ) -> None:
        """Record a tool call and its result."""
        self._calls.append((tool, args if args is not None else {}, result))

    @property
    def calls(self) -> list[tuple[str, dict[str, Any], Any]]:
        return list(self._calls)

    # -- analysis -----------------------------------------------------

    def _key(self, tool: str, args: dict[str, Any]) -> str:
        """Stable cache key for a tool+args pair."""
        sorted_args = sorted(args.items())
        return f"{tool}:{sorted_args}"

    def detect_repeated(self) -> list[tuple[str, dict[str, Any], int]]:
        """Return (tool, args, count) for calls made more than once."""
        counts: dict[str, int] = {}
        first_args: dict[str, tuple[str, dict[str, Any]]] = {}
        for tool, args, _result in self._calls:
            k = self._key(tool, args)
            counts[k] = counts.get(k, 0) + 1
            if k not in first_args:
                first_args[k] = (tool, dict(args))

        return [
            (first_args[k][0], first_args[k][1], cnt)
            for k, cnt in counts.items()
            if cnt > 1
        ]

    def suggest_cache(self) -> list[str]:
        """Return human-readable caching suggestions."""
        repeated = self.detect_repeated()
        suggestions: list[str] = []
        for tool, args, count in repeated:
            arg_str = ", ".join(f"{k}={v!r}" for k, v in sorted(args.items()))
            suggestions.append(
                f"Cache {tool}({arg_str}) — called {count} times with identical args."
            )

        # Suggest caching for read-only tools regardless of repetition
        read_tools = {"Read", "read", "file_read", "Glob", "glob", "Grep", "grep"}
        read_count = sum(1 for t, _, _ in self._calls if t in read_tools)
        if read_count > 3 and not repeated:
            suggestions.append(
                f"{read_count} read-only tool calls detected; consider a read cache layer."
            )

        return suggestions

    def estimate_savings(self) -> dict[str, Any]:
        """Estimate time/calls saved if caching were applied."""
        repeated = self.detect_repeated()
        cacheable_calls = sum(cnt - 1 for _, _, cnt in repeated)
        total = len(self._calls)
        saved_ratio = cacheable_calls / total if total else 0.0
        return {
            "total_calls": total,
            "cacheable_calls": cacheable_calls,
            "unique_calls": total - cacheable_calls,
            "saved_ratio": round(saved_ratio, 4),
            "repeated_patterns": len(repeated),
        }
