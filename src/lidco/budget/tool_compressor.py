"""Compress tool results in conversation history."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompressionRule:
    """How to compress a specific tool's output."""

    tool_name: str
    max_tokens: int = 500
    strategy: str = "truncate"
    keep_head: int = 5
    keep_tail: int = 3


@dataclass(frozen=True)
class CompressedResult:
    """Stats about one compression operation."""

    original_tokens: int
    compressed_tokens: int
    tool_name: str = ""
    truncated: bool = False


_DEFAULT_RULES: dict[str, CompressionRule] = {
    "Read": CompressionRule("Read", max_tokens=500, strategy="head_tail"),
    "Grep": CompressionRule("Grep", max_tokens=300, strategy="top_n"),
    "Bash": CompressionRule("Bash", max_tokens=400, strategy="head_tail"),
    "Glob": CompressionRule("Glob", max_tokens=200, strategy="truncate"),
}


class ToolCompressor:
    """Compress tool-result messages to reclaim context tokens."""

    def __init__(self) -> None:
        self._rules: dict[str, CompressionRule] = dict(_DEFAULT_RULES)

    def add_rule(self, rule: CompressionRule) -> None:
        self._rules = {**self._rules, rule.tool_name: rule}

    # -- core -----------------------------------------------------------------

    def compress(
        self, tool_name: str, content: str
    ) -> tuple[str, CompressedResult]:
        """Compress *content* according to the rule for *tool_name*."""
        original_tokens = self.estimate_tokens(content)
        rule = self._rules.get(tool_name)
        if rule is None or original_tokens <= rule.max_tokens:
            return content, CompressedResult(
                original_tokens=original_tokens,
                compressed_tokens=original_tokens,
                tool_name=tool_name,
            )

        max_chars = rule.max_tokens * 4
        if rule.strategy == "head_tail":
            lines = content.splitlines()
            if len(lines) > rule.keep_head + rule.keep_tail:
                head = lines[: rule.keep_head]
                tail = lines[-rule.keep_tail :] if rule.keep_tail else []
                omitted = len(lines) - rule.keep_head - rule.keep_tail
                compressed = "\n".join(
                    [*head, f"... [{omitted} lines omitted] ...", *tail]
                )
            else:
                compressed = content[:max_chars] + "... [truncated]"
        elif rule.strategy == "top_n":
            lines = content.splitlines()
            kept = lines[: rule.keep_head + rule.keep_tail]
            omitted = max(0, len(lines) - len(kept))
            compressed = "\n".join(
                [*kept, f"... [{omitted} lines omitted] ..."]
            )
        else:  # truncate
            compressed = content[:max_chars] + "... [truncated]"

        compressed_tokens = self.estimate_tokens(compressed)
        return compressed, CompressedResult(
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            tool_name=tool_name,
            truncated=True,
        )

    def compress_messages(
        self, messages: list[dict], keep_recent: int = 3
    ) -> tuple[list[dict], int]:
        """Compress tool results in *messages*, keeping last *keep_recent* full.

        Returns (new_messages, total_tokens_saved).
        """
        # Find tool message indices
        tool_indices = [
            i for i, m in enumerate(messages) if m.get("role") == "tool"
        ]
        # Protect the last keep_recent tool messages
        protected: set[int] = set(tool_indices[-keep_recent:])

        saved = 0
        result: list[dict] = []
        for i, msg in enumerate(messages):
            if msg.get("role") == "tool" and i not in protected:
                tool_name = str(msg.get("name", ""))
                content = str(msg.get("content", ""))
                new_content, stats = self.compress(tool_name, content)
                saved += stats.original_tokens - stats.compressed_tokens
                result = [*result, {**msg, "content": new_content}]
            else:
                result = [*result, msg]

        return result, saved

    @staticmethod
    def estimate_tokens(text: str) -> int:
        return len(text) // 4

    def summary(self) -> str:
        rules = ", ".join(
            f"{r.tool_name}({r.max_tokens})" for r in self._rules.values()
        )
        return f"ToolCompressor: {len(self._rules)} rules — {rules}"
