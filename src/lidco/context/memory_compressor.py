"""Memory auto-compression — Task 313.

When a memory file grows beyond a threshold (default 500 lines), this module
compresses older entries via LLM summarisation, keeping recent entries intact.

Usage::

    compressor = MemoryCompressor(session)
    result = await compressor.maybe_compress(
        path=Path("MEMORY.md"),
        threshold_lines=500,
    )
    if result.compressed:
        print(f"Compressed {result.removed_entries} entries into summary")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lidco.core.session import Session

logger = logging.getLogger(__name__)

_DEFAULT_THRESHOLD = 500
_DEFAULT_KEEP_RECENT = 50  # keep the last N lines intact


@dataclass
class CompressionResult:
    """Result of a memory compression attempt."""

    compressed: bool = False
    original_lines: int = 0
    new_lines: int = 0
    removed_entries: int = 0
    error: str = ""

    @property
    def lines_saved(self) -> int:
        return self.original_lines - self.new_lines


class MemoryCompressor:
    """Compresses large memory files using an LLM summary.

    Args:
        session: Active LIDCO session for LLM access.
        threshold_lines: Trigger compression when file exceeds this line count.
        keep_recent_lines: Number of recent lines to preserve unchanged.
    """

    def __init__(
        self,
        session: "Session | None" = None,
        threshold_lines: int = _DEFAULT_THRESHOLD,
        keep_recent_lines: int = _DEFAULT_KEEP_RECENT,
    ) -> None:
        self._session = session
        self._threshold = threshold_lines
        self._keep_recent = keep_recent_lines

    async def maybe_compress(
        self,
        path: Path,
        threshold_lines: int | None = None,
    ) -> CompressionResult:
        """Compress *path* if it exceeds the line threshold.

        Returns immediately with ``compressed=False`` if under threshold.
        """
        threshold = threshold_lines if threshold_lines is not None else self._threshold
        if not path.exists():
            return CompressionResult(compressed=False)

        lines = path.read_text(encoding="utf-8").splitlines()
        original_lines = len(lines)

        if original_lines < threshold:
            return CompressionResult(
                compressed=False,
                original_lines=original_lines,
                new_lines=original_lines,
            )

        return await self._compress(path, lines)

    async def _compress(self, path: Path, lines: list[str]) -> CompressionResult:
        original_lines = len(lines)
        # Keep the last N lines unchanged; compress everything before that
        keep = min(self._keep_recent, len(lines) - 1) if self._keep_recent > 0 else 0
        recent_lines = lines[-keep:] if keep > 0 else []
        old_lines = lines[: len(lines) - keep]

        if not old_lines:
            return CompressionResult(
                compressed=False,
                original_lines=original_lines,
                new_lines=original_lines,
            )

        old_text = "\n".join(old_lines)

        try:
            summary = await self._summarize(old_text)
        except Exception as exc:
            logger.warning("MemoryCompressor: LLM summarization failed: %s", exc)
            return CompressionResult(
                compressed=False,
                original_lines=original_lines,
                error=str(exc),
            )

        # Build new file: summary header + compressed block + recent lines
        summary_block = (
            "## [Auto-compressed summary]\n"
            f"{summary}\n"
            "<!-- end compressed -->\n"
        )
        new_content = summary_block + "\n" + "\n".join(recent_lines)
        path.write_text(new_content, encoding="utf-8")
        new_lines = len(new_content.splitlines())

        return CompressionResult(
            compressed=True,
            original_lines=original_lines,
            new_lines=new_lines,
            removed_entries=len(old_lines),
        )

    async def _summarize(self, text: str) -> str:
        """Call the LLM to produce a compressed summary of *text*."""
        if self._session is None:
            raise RuntimeError("No session available for LLM summarization")

        llm = getattr(self._session, "llm", None)
        if llm is None:
            raise RuntimeError("Session has no llm attribute")

        system = (
            "You are a memory compressor for an AI coding assistant. "
            "Compress the following memory entries into a concise summary "
            "that preserves ALL key facts, decisions, rules, and patterns. "
            "Organize by topic. Output only the summary."
        )
        resp = await llm.complete(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Compress:\n\n{text[:8000]}"},
            ],
            model=None,
            max_tokens=1000,
        )
        return resp.content.strip() if hasattr(resp, "content") else str(resp).strip()
