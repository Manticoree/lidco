"""Virtual Memory — page-based context swapping (stdlib only).

Provides a page-in / page-out abstraction so context entries can be
evicted to "disk" (an internal dict) and reloaded on demand.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Page:
    """A single page in virtual memory."""

    id: str
    content: str
    last_accessed: float = field(default_factory=time.monotonic)
    in_memory: bool = True


class VirtualMemory:
    """Page-based virtual memory for context window management."""

    def __init__(self) -> None:
        self._pages: dict[str, Page] = {}
        self._disk: dict[str, str] = {}  # page_id -> content (swapped out)
        self._page_in_count: int = 0
        self._page_out_count: int = 0

    # ------------------------------------------------------------------ #
    # Core operations                                                     #
    # ------------------------------------------------------------------ #

    def add_page(self, page_id: str, content: str) -> None:
        """Add a new in-memory page."""
        page = Page(id=page_id, content=content, last_accessed=time.monotonic(), in_memory=True)
        self._pages = {**self._pages, page_id: page}

    def page_in(self, page_id: str) -> str | None:
        """Load a page from disk into memory.  Returns content or None."""
        page = self._pages.get(page_id)
        if page is None:
            return None
        if page.in_memory:
            return page.content
        # Restore from disk
        content = self._disk.pop(page_id, page.content)
        updated = Page(
            id=page.id,
            content=content,
            last_accessed=time.monotonic(),
            in_memory=True,
        )
        self._pages = {**self._pages, page_id: updated}
        self._page_in_count += 1
        return content

    def page_out(self, page_id: str) -> bool:
        """Swap a page to disk.  Returns True if successful."""
        page = self._pages.get(page_id)
        if page is None or not page.in_memory:
            return False
        self._disk[page_id] = page.content
        updated = Page(
            id=page.id,
            content=page.content,
            last_accessed=page.last_accessed,
            in_memory=False,
        )
        self._pages = {**self._pages, page_id: updated}
        self._page_out_count += 1
        return True

    def access(self, page_id: str) -> str | None:
        """Access a page — page_in if needed, update last_accessed."""
        page = self._pages.get(page_id)
        if page is None:
            return None
        if not page.in_memory:
            return self.page_in(page_id)
        # Update last_accessed
        updated = Page(
            id=page.id,
            content=page.content,
            last_accessed=time.monotonic(),
            in_memory=True,
        )
        self._pages = {**self._pages, page_id: updated}
        return page.content

    # ------------------------------------------------------------------ #
    # Working set & eviction                                              #
    # ------------------------------------------------------------------ #

    def working_set(self) -> list[str]:
        """Return ids of in-memory pages."""
        return [pid for pid, p in self._pages.items() if p.in_memory]

    def evict_lru(self) -> str | None:
        """Evict the least recently used in-memory page.  Returns its id."""
        in_mem = [p for p in self._pages.values() if p.in_memory]
        if not in_mem:
            return None
        victim = min(in_mem, key=lambda p: p.last_accessed)
        self.page_out(victim.id)
        return victim.id

    # ------------------------------------------------------------------ #
    # Introspection                                                       #
    # ------------------------------------------------------------------ #

    def get_page(self, page_id: str) -> Page | None:
        return self._pages.get(page_id)

    def stats(self) -> dict[str, Any]:
        in_mem = sum(1 for p in self._pages.values() if p.in_memory)
        on_disk = sum(1 for p in self._pages.values() if not p.in_memory)
        return {
            "total_pages": len(self._pages),
            "in_memory": in_mem,
            "on_disk": on_disk,
            "page_in_count": self._page_in_count,
            "page_out_count": self._page_out_count,
        }
