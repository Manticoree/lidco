"""Incremental context compaction — compact oldest turns first."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CompactionResult:
    """Outcome of an incremental compaction pass."""

    compacted: tuple[dict, ...] = ()
    removed_count: int = 0
    saved_tokens: int = 0
    watermark: int = 0


class IncrementalCompactor:
    """Compact conversation messages incrementally from a watermark."""

    def __init__(self, watermark: int = 0) -> None:
        self._watermark = watermark

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    @property
    def watermark(self) -> int:
        return self._watermark

    def compact(
        self,
        messages: list[dict],
        target_tokens: int,
    ) -> CompactionResult:
        """Compact from watermark forward until under *target_tokens*."""
        if not messages:
            return CompactionResult(watermark=self._watermark)

        current_tokens = self.estimate_tokens(messages)
        if current_tokens <= target_tokens:
            return CompactionResult(
                compacted=tuple(messages),
                watermark=self._watermark,
            )

        # Work on a copy — never mutate the original
        result: list[dict] = list(messages)
        removed = 0
        saved = 0
        idx = self._watermark

        while idx < len(result) and self.estimate_tokens(result) > target_tokens:
            msg = result[idx]
            role = msg.get("role", "")

            # Never compact system or user messages
            if role in ("system", "user"):
                idx += 1
                continue

            content = msg.get("content", "")
            old_tokens = max(1, len(content) // 4)

            if role == "tool":
                # Summarize tool result to first line
                first_line = content.split("\n", 1)[0] if content else ""
                new_msg = {**msg, "content": first_line}
                result = result[:idx] + [new_msg] + result[idx + 1:]
                new_tokens = max(1, len(first_line) // 4)
                saved += old_tokens - new_tokens
                idx += 1
            else:
                # Remove assistant filler
                if old_tokens < 10:
                    result = result[:idx] + result[idx + 1:]
                    removed += 1
                    saved += old_tokens
                else:
                    idx += 1

        # Merge adjacent same-role messages
        result = self._merge_adjacent(result)
        self._watermark = len(result)

        return CompactionResult(
            compacted=tuple(result),
            removed_count=removed,
            saved_tokens=saved,
            watermark=self._watermark,
        )

    def merge_tool_results(self, messages: list[dict]) -> list[dict]:
        """Merge consecutive tool-role messages into one summary."""
        if not messages:
            return []

        merged: list[dict] = []
        for msg in messages:
            if (
                merged
                and merged[-1].get("role") == "tool"
                and msg.get("role") == "tool"
            ):
                prev_content = merged[-1].get("content", "")
                cur_content = msg.get("content", "")
                combined = f"{prev_content}\n---\n{cur_content}"
                merged[-1] = {**merged[-1], "content": combined}
            else:
                merged.append(dict(msg))
        return merged

    def estimate_tokens(self, messages: list[dict]) -> int:
        """Sum len(content)//4 for all messages."""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            total += max(1, len(content) // 4)
        return total

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _merge_adjacent(messages: list[dict]) -> list[dict]:
        """Merge adjacent messages with the same role."""
        if not messages:
            return []
        merged: list[dict] = [dict(messages[0])]
        for msg in messages[1:]:
            if merged[-1].get("role") == msg.get("role"):
                prev = merged[-1].get("content", "")
                cur = msg.get("content", "")
                merged[-1] = {**merged[-1], "content": f"{prev}\n{cur}"}
            else:
                merged.append(dict(msg))
        return merged
