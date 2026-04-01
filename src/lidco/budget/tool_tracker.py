"""Per-tool token consumption tracking."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolUsage:
    """Immutable snapshot of a single tool's token usage."""

    tool_name: str
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ToolTokenTracker:
    """Accumulates per-tool token usage across a session."""

    def __init__(self) -> None:
        self._usage: dict[str, dict[str, int]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self, tool_name: str, input_tokens: int = 0, output_tokens: int = 0
    ) -> None:
        """Record a tool invocation and its token cost."""
        prev = self._usage.get(tool_name, {
            "calls": 0, "input_tokens": 0, "output_tokens": 0,
        })
        self._usage = {
            **self._usage,
            tool_name: {
                "calls": prev["calls"] + 1,
                "input_tokens": prev["input_tokens"] + input_tokens,
                "output_tokens": prev["output_tokens"] + output_tokens,
            },
        }

    def get_usage(self, tool_name: str) -> ToolUsage | None:
        """Return usage for a single tool, or ``None`` if unseen."""
        entry = self._usage.get(tool_name)
        if entry is None:
            return None
        return ToolUsage(
            tool_name=tool_name,
            calls=entry["calls"],
            input_tokens=entry["input_tokens"],
            output_tokens=entry["output_tokens"],
            total_tokens=entry["input_tokens"] + entry["output_tokens"],
        )

    def get_all(self) -> list[ToolUsage]:
        """Return all tool usages sorted by total_tokens descending."""
        items = [self.get_usage(name) for name in self._usage]
        return sorted(
            [u for u in items if u is not None],
            key=lambda u: u.total_tokens,
            reverse=True,
        )

    def hottest(self, limit: int = 5) -> list[ToolUsage]:
        """Return the top *limit* tools by total token consumption."""
        return self.get_all()[:limit]

    def total_tokens(self) -> int:
        """Sum of all token usage across every tool."""
        return sum(
            e["input_tokens"] + e["output_tokens"]
            for e in self._usage.values()
        )

    def reset(self) -> None:
        """Clear all recorded usage."""
        self._usage = {}

    def summary(self) -> str:
        """Human-readable one-liner: ``Read: 15 calls, 45,230 tokens | ...``."""
        if not self._usage:
            return "No tool usage recorded."
        parts: list[str] = []
        for usage in self.get_all():
            parts.append(
                f"{usage.tool_name}: {usage.calls} calls, "
                f"{usage.total_tokens:,} tokens"
            )
        return " | ".join(parts)
