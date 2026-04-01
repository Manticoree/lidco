"""Truncate tool results based on remaining budget."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TruncationResult:
    """Metadata about a truncation operation."""

    original_tokens: int
    truncated_tokens: int
    strategy: str = ""
    truncated: bool = False


class AdaptiveTruncator:
    """Truncate tool output adaptively based on remaining token budget.

    Different tools get different truncation strategies:
    - Read / Bash  → head_tail (keep first 60% + last 40%)
    - Grep         → top_lines (keep first N lines)
    - Others       → hard_truncate (keep first N chars)
    """

    _HEAD_TAIL_TOOLS = frozenset({"Read", "Bash"})
    _TOP_LINES_TOOLS = frozenset({"Grep"})

    def __init__(self, default_max: int = 2000) -> None:
        self._default_max = default_max
        self._tool_limits: dict[str, int] = {
            "Read": 1500,
            "Grep": 1000,
            "Bash": 1200,
            "Glob": 500,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def truncate(
        self, tool_name: str, content: str, budget_remaining: int
    ) -> tuple[str, TruncationResult]:
        """Return *(truncated_content, metadata)*."""
        original_tokens = self.estimate_tokens(content)

        if original_tokens <= budget_remaining:
            tool_limit = self._tool_limits.get(tool_name, self._default_max)
            if original_tokens <= tool_limit:
                return content, TruncationResult(
                    original_tokens=original_tokens,
                    truncated_tokens=original_tokens,
                )

        tool_limit = self._tool_limits.get(tool_name, self._default_max)
        adaptive_max = min(tool_limit, max(budget_remaining // 2, 1))

        if tool_name in self._HEAD_TAIL_TOOLS:
            text = self._head_tail(content, adaptive_max)
            strategy = "head_tail"
        elif tool_name in self._TOP_LINES_TOOLS:
            text = self._top_lines(content, adaptive_max)
            strategy = "top_lines"
        else:
            text = self._hard_truncate(content, adaptive_max)
            strategy = "hard_truncate"

        return text, TruncationResult(
            original_tokens=original_tokens,
            truncated_tokens=self.estimate_tokens(text),
            strategy=strategy,
            truncated=True,
        )

    def set_limit(self, tool_name: str, max_tokens: int) -> None:
        """Override the per-tool token limit."""
        self._tool_limits = {**self._tool_limits, tool_name: max_tokens}

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate: 1 token ≈ 4 characters."""
        return len(text) // 4

    def summary(self) -> str:
        """Human-readable summary."""
        limits = ", ".join(
            f"{k}={v}" for k, v in sorted(self._tool_limits.items())
        )
        return f"AdaptiveTruncator: default_max={self._default_max}, limits=[{limits}]"

    # ------------------------------------------------------------------
    # Strategies
    # ------------------------------------------------------------------

    def _head_tail(self, text: str, max_tokens: int) -> str:
        """Keep first 60% and last 40% of allowed lines."""
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text
        lines = text.splitlines(keepends=True)
        total_allowed = max(1, max_chars // max(1, (len(text) // len(lines) if lines else 1)))
        head_count = max(1, int(total_allowed * 0.6))
        tail_count = max(1, total_allowed - head_count)
        if head_count + tail_count >= len(lines):
            return text
        head = lines[:head_count]
        tail = lines[-tail_count:]
        return "".join(head) + "\n... [truncated] ...\n" + "".join(tail)

    def _top_lines(self, text: str, max_tokens: int) -> str:
        """Keep first N lines that fit within *max_tokens*."""
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text
        lines = text.splitlines(keepends=True)
        result: list[str] = []
        total = 0
        for line in lines:
            if total + len(line) > max_chars:
                break
            result.append(line)
            total += len(line)
        return "".join(result) + "\n... [truncated] ..."

    def _hard_truncate(self, text: str, max_tokens: int) -> str:
        """Keep first *max_tokens * 4* characters."""
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n... [truncated] ..."
