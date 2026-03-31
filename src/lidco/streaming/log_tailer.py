"""Log tailer — tail / follow / grep over a line buffer."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable

from lidco.streaming.line_buffer import LineBuffer


@dataclass
class TailEntry:
    """A single tail entry."""

    line: str
    line_number: int
    timestamp: float
    matched: bool


class LogTailer:
    """Tail, follow, and grep over a :class:`LineBuffer`.

    Parameters
    ----------
    buffer:
        Underlying buffer.  A fresh one is created if omitted.
    """

    def __init__(self, buffer: LineBuffer | None = None) -> None:
        self._buffer = buffer if buffer is not None else LineBuffer()
        self._followers: list[Callable[[TailEntry], None]] = []
        self._line_counter: int = 0

    # ------------------------------------------------------------------
    # Tail
    # ------------------------------------------------------------------

    def tail(self, n: int = 10) -> list[TailEntry]:
        """Return the last *n* lines as :class:`TailEntry` objects."""
        lines = self._buffer.read_lines(n)
        return [
            TailEntry(
                line=bl.text,
                line_number=bl.line_number,
                timestamp=bl.timestamp,
                matched=False,
            )
            for bl in lines
        ]

    # ------------------------------------------------------------------
    # Follow / unfollow
    # ------------------------------------------------------------------

    def follow(self, callback: Callable[[TailEntry], None]) -> None:
        """Register *callback* to be called for every new line."""
        if callback not in self._followers:
            self._followers.append(callback)

    def unfollow(self, callback: Callable[[TailEntry], None]) -> None:
        """Remove a previously registered follower."""
        try:
            self._followers.remove(callback)
        except ValueError:
            pass

    @property
    def follower_count(self) -> int:
        """Number of active followers."""
        return len(self._followers)

    # ------------------------------------------------------------------
    # Add line
    # ------------------------------------------------------------------

    def add_line(self, text: str) -> None:
        """Feed a line into the buffer and notify followers."""
        self._line_counter += 1
        now = time.time()
        self._buffer.write(text)
        entry = TailEntry(
            line=text,
            line_number=self._line_counter,
            timestamp=now,
            matched=False,
        )
        for cb in list(self._followers):
            cb(entry)

    # ------------------------------------------------------------------
    # Grep
    # ------------------------------------------------------------------

    def grep(self, pattern: str, last_n: int | None = None) -> list[TailEntry]:
        """Filter buffered lines by regex *pattern*.

        Parameters
        ----------
        pattern:
            Regular expression to match against each line.
        last_n:
            If given, only consider the last *n* buffered lines.
        """
        compiled = re.compile(pattern)
        lines = self._buffer.read_lines(last_n)
        results: list[TailEntry] = []
        for bl in lines:
            if compiled.search(bl.text):
                results.append(
                    TailEntry(
                        line=bl.text,
                        line_number=bl.line_number,
                        timestamp=bl.timestamp,
                        matched=True,
                    )
                )
        return results
