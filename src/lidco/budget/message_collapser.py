"""Merge similar adjacent messages to save context tokens."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CollapseResult:
    """Result of collapsing messages."""

    original_count: int
    collapsed_count: int
    tokens_saved: int = 0
    merges: tuple[tuple[int, int], ...] = ()


class MessageCollapser:
    """Collapse adjacent same-role messages to save tokens."""

    def __init__(self, similarity_threshold: float = 0.7) -> None:
        self._threshold = similarity_threshold

    def collapse(
        self, messages: list[dict]
    ) -> tuple[list[dict], CollapseResult]:
        """Merge adjacent same-role messages.

        Tool results are combined into summaries; short assistant
        confirmations ("OK", "Done", "Sure") are merged into one.
        """
        if not messages:
            return [], CollapseResult(original_count=0, collapsed_count=0)

        groups: list[list[dict]] = []
        merges: list[tuple[int, int]] = []
        current_group: list[dict] = [messages[0]]

        for msg in messages[1:]:
            prev = current_group[-1]
            if msg.get("role") == prev.get("role") and msg.get("role") != "system":
                current_group.append(msg)
            else:
                groups.append(current_group)
                current_group = [msg]
        groups.append(current_group)

        result: list[dict] = []
        idx = 0
        for group in groups:
            if len(group) == 1:
                result.append(group[0])
            else:
                merged = self._merge_messages(group)
                result.append(merged)
                merges.append((idx, idx + len(group) - 1))
            idx += len(group)

        original_tokens = sum(
            self.estimate_tokens(m.get("content", "")) for m in messages
        )
        collapsed_tokens = sum(
            self.estimate_tokens(m.get("content", "")) for m in result
        )
        return result, CollapseResult(
            original_count=len(messages),
            collapsed_count=len(result),
            tokens_saved=max(0, original_tokens - collapsed_tokens),
            merges=tuple(merges),
        )

    def _are_similar(self, a: str, b: str) -> bool:
        """Jaccard similarity on word sets exceeds threshold."""
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a and not words_b:
            return True
        union = words_a | words_b
        if not union:
            return True
        return len(words_a & words_b) / len(union) >= self._threshold

    def _merge_messages(self, msgs: list[dict]) -> dict:
        """Combine content with separator, keep role from first."""
        contents = [m.get("content", "") for m in msgs]
        # For short assistant confirmations, deduplicate
        short = {"ok", "done", "sure", "yes", "got it", "understood"}
        if msgs[0].get("role") == "assistant" and all(
            c.strip().lower().rstrip(".!") in short for c in contents
        ):
            merged_content = contents[0]
        else:
            merged_content = "\n---\n".join(c for c in contents if c)
        return {"role": msgs[0].get("role", "user"), "content": merged_content}

    def collapse_tool_results(self, messages: list[dict]) -> list[dict]:
        """Merge consecutive tool-role messages into summaries."""
        if not messages:
            return []

        result: list[dict] = []
        tool_group: list[dict] = []

        def _flush_tools() -> None:
            if not tool_group:
                return
            if len(tool_group) == 1:
                result.append(tool_group[0])
            else:
                lines: list[str] = []
                for i, tm in enumerate(tool_group, 1):
                    content = tm.get("content", "")
                    first_line = content.split("\n")[0][:80] if content else ""
                    lines.append(f"[tool{i}: {first_line}]")
                summary = f"{len(tool_group)} tool results: " + ", ".join(lines)
                result.append({"role": "tool", "content": summary})
            tool_group.clear()

        for msg in messages:
            if msg.get("role") == "tool":
                tool_group.append(msg)
            else:
                _flush_tools()
                result.append(msg)
        _flush_tools()
        return result

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate: ~4 chars per token."""
        return len(text) // 4

    def summary(self, result: CollapseResult) -> str:
        """Human-readable summary of collapse result."""
        return (
            f"Collapsed {result.original_count} -> {result.collapsed_count} messages, "
            f"saved ~{result.tokens_saved} tokens, {len(result.merges)} merges"
        )
