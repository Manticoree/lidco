"""Output paginator — split lines into pages."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass


@dataclass
class Page:
    """A single page of output."""

    content: list[str]
    page_number: int
    total_pages: int
    has_next: bool
    has_prev: bool


class OutputPaginator:
    """Paginate a list of lines into fixed-size pages.

    Parameters
    ----------
    lines:
        The full list of output lines.
    page_size:
        Number of lines per page.
    """

    def __init__(self, lines: list[str], page_size: int = 20) -> None:
        self._lines = list(lines)
        self._page_size = max(1, page_size)
        self._current: int = 1

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def total_pages(self) -> int:
        """Total number of pages."""
        if not self._lines:
            return 1
        return math.ceil(len(self._lines) / self._page_size)

    @property
    def current_page_number(self) -> int:
        """1-indexed current page number."""
        return self._current

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def page(self, n: int) -> Page:
        """Return page *n* (1-indexed).

        Out-of-range page numbers are clamped to valid bounds.
        """
        total = self.total_pages
        n = max(1, min(n, total))
        self._current = n
        start = (n - 1) * self._page_size
        end = start + self._page_size
        return Page(
            content=self._lines[start:end],
            page_number=n,
            total_pages=total,
            has_next=n < total,
            has_prev=n > 1,
        )

    def next_page(self) -> Page:
        """Advance the cursor and return the next page."""
        return self.page(self._current + 1)

    def prev_page(self) -> Page:
        """Move the cursor back and return the previous page."""
        return self.page(self._current - 1)

    def first_page(self) -> Page:
        """Return the first page."""
        return self.page(1)

    def last_page(self) -> Page:
        """Return the last page."""
        return self.page(self.total_pages)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_pages(self, pattern: str) -> list[int]:
        """Return 1-indexed page numbers that contain at least one match."""
        compiled = re.compile(pattern)
        result: list[int] = []
        total = self.total_pages
        for p in range(1, total + 1):
            start = (p - 1) * self._page_size
            end = start + self._page_size
            for line in self._lines[start:end]:
                if compiled.search(line):
                    result.append(p)
                    break
        return result
