"""Command palette with fuzzy search and recent tracking."""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class PaletteEntry:
    """An entry in the command palette."""

    command: str
    description: str
    category: str = "general"
    shortcut: str = ""
    score: float = 0.0


class CommandPalette:
    """Fuzzy-search command palette; recent commands; categorized."""

    def __init__(self) -> None:
        self._entries: dict[str, PaletteEntry] = {}
        self._recent: deque[str] = deque(maxlen=100)

    # ------------------------------------------------------------------
    # fuzzy helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fuzzy_score(query: str, text: str) -> float:
        """Simple fuzzy matching score.  Higher is better; 0 means no match."""
        q = query.lower()
        t = text.lower()
        # exact substring
        if q in t:
            return 1.0 + (len(q) / max(len(t), 1))
        # subsequence match
        qi = 0
        for ch in t:
            if qi < len(q) and ch == q[qi]:
                qi += 1
        if qi == len(q):
            return len(q) / max(len(t), 1)
        return 0.0

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def register(self, command: str, description: str, category: str = "general", shortcut: str = "") -> PaletteEntry:
        entry = PaletteEntry(command=command, description=description, category=category, shortcut=shortcut)
        self._entries[command] = entry
        return entry

    def unregister(self, command: str) -> bool:
        if command in self._entries:
            del self._entries[command]
            return True
        return False

    def search(self, query: str, limit: int = 20) -> list[PaletteEntry]:
        scored: list[tuple[float, PaletteEntry]] = []
        for entry in self._entries.values():
            # score against command + description
            s1 = self._fuzzy_score(query, entry.command)
            s2 = self._fuzzy_score(query, entry.description)
            best = max(s1, s2)
            if best > 0:
                scored.append((best, entry))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [
            PaletteEntry(
                command=e.command,
                description=e.description,
                category=e.category,
                shortcut=e.shortcut,
                score=round(sc, 4),
            )
            for sc, e in scored[:limit]
        ]

    def execute(self, command: str) -> bool:
        if command not in self._entries:
            return False
        self._recent.appendleft(command)
        return True

    def recent(self, limit: int = 10) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for cmd in self._recent:
            if cmd not in seen:
                seen.add(cmd)
                result.append(cmd)
            if len(result) >= limit:
                break
        return result

    def by_category(self, category: str) -> list[PaletteEntry]:
        return [e for e in self._entries.values() if e.category == category]

    def categories(self) -> list[str]:
        return sorted({e.category for e in self._entries.values()})

    def all_entries(self) -> list[PaletteEntry]:
        return list(self._entries.values())

    def summary(self) -> dict:
        return {
            "total": len(self._entries),
            "categories": self.categories(),
            "recent_count": len(self._recent),
        }
