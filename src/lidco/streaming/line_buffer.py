"""Line buffer for streaming output."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field


@dataclass
class BufferedLine:
    """A single buffered line."""

    text: str
    timestamp: float
    line_number: int
    source: str = "default"


class LineBuffer:
    """Buffer that accumulates text split into lines.

    Parameters
    ----------
    max_lines:
        Maximum number of lines to retain.  Oldest lines are discarded when
        the limit is exceeded.
    """

    def __init__(self, max_lines: int = 1000) -> None:
        self._max_lines = max_lines
        self._lines: list[BufferedLine] = []
        self._total_written: int = 0
        self._read_cursor: int = 0  # index into _lines for read_new()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write(self, text: str, source: str = "default") -> None:
        """Split *text* on newlines and buffer each resulting line."""
        now = time.time()
        parts = text.split("\n")
        for part in parts:
            self._total_written += 1
            line = BufferedLine(
                text=part,
                timestamp=now,
                line_number=self._total_written,
                source=source,
            )
            self._lines.append(line)
        # Trim oldest if over limit
        if len(self._lines) > self._max_lines:
            excess = len(self._lines) - self._max_lines
            self._lines = self._lines[excess:]
            # Adjust cursor so it doesn't point past valid entries
            self._read_cursor = max(0, self._read_cursor - excess)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read_lines(self, n: int | None = None) -> list[BufferedLine]:
        """Return the last *n* lines (or all if *n* is ``None``)."""
        if n is None:
            return list(self._lines)
        return list(self._lines[-n:])

    def read_new(self) -> list[BufferedLine]:
        """Return lines added since the last call to :meth:`read_new`."""
        new = list(self._lines[self._read_cursor:])
        self._read_cursor = len(self._lines)
        return new

    def flush(self) -> list[BufferedLine]:
        """Return all buffered lines and clear the buffer."""
        result = list(self._lines)
        self._lines = []
        self._read_cursor = 0
        return result

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @property
    def line_count(self) -> int:
        """Number of lines currently buffered."""
        return len(self._lines)

    @property
    def is_empty(self) -> bool:
        """Whether the buffer is empty."""
        return len(self._lines) == 0

    def search(self, pattern: str) -> list[BufferedLine]:
        """Return lines whose text matches *pattern* (regex)."""
        compiled = re.compile(pattern)
        return [ln for ln in self._lines if compiled.search(ln.text)]

    def clear(self) -> None:
        """Remove all buffered lines."""
        self._lines = []
        self._read_cursor = 0
