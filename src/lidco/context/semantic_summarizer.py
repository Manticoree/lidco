"""Semantic summarizer for conversation context compression."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SummaryEntry:
    """A single summarized turn."""

    role: str
    content: str
    turn_index: int = 0
    importance: float = 0.5


@dataclass(frozen=True)
class SummaryResult:
    """Result of summarising a conversation."""

    entries: tuple[SummaryEntry, ...] = ()
    original_tokens: int = 0
    compressed_tokens: int = 0
    ratio: float = 0.0


_CODE_FENCE = re.compile(r"```[\s\S]*?```")


class SemanticSummarizer:
    """Compress conversation turns while preserving key content."""

    def __init__(self, max_ratio: float = 0.5) -> None:
        self._max_ratio = max_ratio
        self._original_tokens = 0
        self._compressed_tokens = 0

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def summarize(self, turns: list[dict[str, str]]) -> SummaryResult:
        """Summarize conversation turns, keeping code and system messages."""
        if not turns:
            return SummaryResult()

        original_tokens = sum(self._estimate_tokens(t.get("content", "")) for t in turns)
        entries: list[SummaryEntry] = []

        for idx, turn in enumerate(turns):
            role = turn.get("role", "user")
            content = turn.get("content", "")
            importance = self.score_importance(turn)
            compressed = content if role == "system" else self.compress_turn(content, self._max_ratio)
            entries.append(SummaryEntry(
                role=role,
                content=compressed,
                turn_index=idx,
                importance=importance,
            ))

        compressed_tokens = sum(self._estimate_tokens(e.content) for e in entries)
        ratio = compressed_tokens / original_tokens if original_tokens > 0 else 0.0
        self._original_tokens = original_tokens
        self._compressed_tokens = compressed_tokens

        return SummaryResult(
            entries=tuple(entries),
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            ratio=round(ratio, 4),
        )

    def score_importance(self, turn: dict[str, str]) -> float:
        """Score 0.0-1.0 based on content heuristics."""
        role = turn.get("role", "user")
        content = turn.get("content", "")

        if role == "system":
            return 1.0
        if "error" in content.lower() or "traceback" in content.lower():
            return 0.9
        if "```" in content:
            return 0.8
        if role == "user" and content.strip().endswith("?"):
            return 0.7
        if len(content) < 40:
            return 0.3
        return 0.5

    def compress_turn(self, content: str, target_ratio: float = 0.5) -> str:
        """Compress a single turn: keep first/last line + code blocks."""
        if not content:
            return content

        # Extract code blocks to preserve them
        code_blocks = _CODE_FENCE.findall(content)
        stripped = _CODE_FENCE.sub("", content).strip()
        lines = stripped.splitlines()

        if len(lines) <= 3:
            compressed = stripped
        else:
            first_line = lines[0]
            last_line = lines[-1]
            compressed = f"{first_line}\n[...{len(lines) - 2} lines omitted...]\n{last_line}"

        if code_blocks:
            compressed = compressed + "\n" + "\n".join(code_blocks)

        # Ensure we don't exceed target ratio
        orig_len = len(content)
        target_len = int(orig_len * target_ratio)
        if len(compressed) > target_len > 0:
            compressed = compressed[:target_len]

        return compressed

    def stats(self) -> dict:
        """Return compression statistics."""
        return {
            "original_tokens": self._original_tokens,
            "compressed_tokens": self._compressed_tokens,
            "ratio": round(
                self._compressed_tokens / self._original_tokens
                if self._original_tokens > 0
                else 0.0,
                4,
            ),
            "max_ratio": self._max_ratio,
        }

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len(text) // 4)
