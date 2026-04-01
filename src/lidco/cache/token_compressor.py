"""Token Compressor — reduce token usage via deduplication and summarization."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CompressionResult:
    """Result of a text compression operation."""

    original_tokens: int
    compressed_tokens: int
    ratio: float
    text: str


class TokenCompressor:
    """Compress prompts to reduce token usage.

    Uses whitespace normalization, duplicate removal, and pattern
    summarization to shrink prompts while preserving semantics.
    """

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimate (~4 chars per token)."""
        return max(1, len(text) // 4)

    def compress(self, text: str) -> CompressionResult:
        """Compress *text* by normalizing whitespace and removing redundancy."""
        original_tokens = self._estimate_tokens(text)
        # Normalize multiple blank lines to single
        compressed = re.sub(r"\n{3,}", "\n\n", text)
        # Normalize multiple spaces to single
        compressed = re.sub(r"[ \t]{2,}", " ", compressed)
        compressed = compressed.strip()
        compressed_tokens = self._estimate_tokens(compressed)
        ratio = compressed_tokens / original_tokens if original_tokens else 1.0
        return CompressionResult(
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            ratio=round(ratio, 4),
            text=compressed,
        )

    def dedup_reads(self, entries: tuple[str, ...]) -> tuple[str, ...]:
        """Remove duplicate entries preserving order."""
        seen: set[str] = set()
        result: list[str] = []
        for entry in entries:
            if entry not in seen:
                seen.add(entry)
                result.append(entry)
        return tuple(result)

    def summarize_pattern(self, texts: tuple[str, ...]) -> str:
        """Summarize repeated patterns across *texts*.

        Returns a single string describing the common structure.
        """
        if not texts:
            return ""
        if len(texts) == 1:
            return texts[0]
        # Find common prefix
        prefix = texts[0]
        for t in texts[1:]:
            while not t.startswith(prefix) and prefix:
                prefix = prefix[:-1]
        # Find common suffix
        suffix = texts[0]
        for t in texts[1:]:
            while not t.endswith(suffix) and suffix:
                suffix = suffix[1:]
        unique_count = len(set(texts))
        return (
            f"[{unique_count} variants] "
            f"prefix='{prefix[:50]}' suffix='{suffix[:50]}'"
        )


__all__ = ["CompressionResult", "TokenCompressor"]
