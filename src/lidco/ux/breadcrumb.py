"""Q145 Task 860: Breadcrumb navigation trail."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Crumb:
    """A single breadcrumb entry."""

    label: str
    context: str
    timestamp: float


class Breadcrumb:
    """Manages a navigation breadcrumb trail."""

    def __init__(self, max_depth: int = 20) -> None:
        self._max_depth = max_depth
        self._trail: list[Crumb] = []

    def push(self, label: str, context: str = "") -> None:
        """Add a crumb to the trail."""
        crumb = Crumb(label=label, context=context, timestamp=time.time())
        self._trail.append(crumb)
        if len(self._trail) > self._max_depth:
            self._trail = self._trail[-self._max_depth :]

    def pop(self) -> Optional[Crumb]:
        """Remove and return the last crumb, or None if empty."""
        if not self._trail:
            return None
        return self._trail.pop()

    def current(self) -> Optional[Crumb]:
        """Peek at the last crumb without removing it."""
        if not self._trail:
            return None
        return self._trail[-1]

    def trail(self) -> list[Crumb]:
        """Return the full breadcrumb trail."""
        return list(self._trail)

    def render(self, separator: str = " > ") -> str:
        """Render the trail as a string like ``Home > Project > src``."""
        if not self._trail:
            return ""
        return separator.join(c.label for c in self._trail)

    @property
    def depth(self) -> int:
        """Number of crumbs in the trail."""
        return len(self._trail)

    def go_back(self, n: int = 1) -> list[Crumb]:
        """Pop *n* crumbs and return them (most recent first)."""
        removed: list[Crumb] = []
        for _ in range(n):
            crumb = self.pop()
            if crumb is None:
                break
            removed.append(crumb)
        return removed

    def clear(self) -> None:
        """Remove all crumbs."""
        self._trail.clear()
