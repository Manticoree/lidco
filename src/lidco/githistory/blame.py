"""BlameIntelligence — smart blame, skip-formatting, original-author lookup."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class BlameLine:
    """Single blame attribution for one line."""

    hash: str
    author: str
    date: datetime
    line_no: int
    content: str


@dataclass(frozen=True)
class Annotation:
    """Enriched annotation combining blame + metadata."""

    line_no: int
    content: str
    author: str
    hash: str
    date: datetime
    age_days: float = 0.0


# Patterns that indicate formatting-only commits (whitespace, imports, etc.)
_FORMATTING_PATTERNS = frozenset({
    "format",
    "fmt",
    "lint",
    "prettier",
    "black",
    "style",
    "whitespace",
    "indent",
    "reformat",
})


class BlameIntelligence:
    """High-level blame analysis with skip-formatting and original-author lookup."""

    def __init__(self) -> None:
        self._blame_data: dict[str, list[BlameLine]] = {}
        self._commit_messages: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Data ingestion
    # ------------------------------------------------------------------

    def set_blame(self, file: str, lines: list[BlameLine]) -> None:
        """Register blame data for a file."""
        self._blame_data[file] = list(lines)

    def set_commit_message(self, hash: str, message: str) -> None:
        """Register a commit message for formatting-skip logic."""
        self._commit_messages[hash] = message

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def blame(self, file: str, lines: tuple[int, int] | None = None) -> list[BlameLine]:
        """Return blame lines for *file*, optionally filtered to a line range."""
        data = self._blame_data.get(file, [])
        if lines is None:
            return list(data)
        start, end = lines
        return [bl for bl in data if start <= bl.line_no <= end]

    def skip_formatting(self, blame_lines: list[BlameLine]) -> list[BlameLine]:
        """Filter out blame lines whose commit message looks like formatting-only."""
        result: list[BlameLine] = []
        for bl in blame_lines:
            msg = self._commit_messages.get(bl.hash, "").lower()
            if any(pat in msg for pat in _FORMATTING_PATTERNS):
                continue
            result.append(bl)
        return result

    def find_original_author(self, file: str, line: int) -> str:
        """Return the author of the *non-formatting* commit that last touched *line*."""
        data = self._blame_data.get(file, [])
        candidates = [bl for bl in data if bl.line_no == line]
        meaningful = self.skip_formatting(candidates)
        if meaningful:
            return meaningful[0].author
        if candidates:
            return candidates[0].author
        return "unknown"

    def annotate(self, file: str) -> list[Annotation]:
        """Return annotated lines for the entire file."""
        data = self._blame_data.get(file, [])
        now = datetime.now()
        result: list[Annotation] = []
        for bl in data:
            age_days = (now - bl.date).total_seconds() / 86400.0
            result.append(
                Annotation(
                    line_no=bl.line_no,
                    content=bl.content,
                    author=bl.author,
                    hash=bl.hash,
                    date=bl.date,
                    age_days=round(age_days, 2),
                )
            )
        return result
