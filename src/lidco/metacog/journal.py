"""LearningJournal — log lessons learned per session with pattern extraction."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class JournalEntry:
    """A single lesson learned."""

    entry_id: str
    session_id: str
    lesson: str
    category: str  # "technique", "mistake", "insight", "pattern"
    tags: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    impact: str = "medium"  # "low", "medium", "high"


class LearningJournal:
    """Log and retrieve lessons learned across sessions."""

    def __init__(self, max_entries: int = 500) -> None:
        self._entries: list[JournalEntry] = []
        self._max_entries = max_entries
        self._counter = 0

    def log(
        self,
        session_id: str,
        lesson: str,
        category: str = "insight",
        tags: list[str] | None = None,
        impact: str = "medium",
    ) -> JournalEntry:
        """Log a new lesson."""
        self._counter += 1
        entry = JournalEntry(
            entry_id=f"j-{self._counter}",
            session_id=session_id,
            lesson=lesson,
            category=category,
            tags=tags or [],
            impact=impact,
        )
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]
        return entry

    def entries(self, session_id: str | None = None) -> list[JournalEntry]:
        """Get entries, optionally filtered by session."""
        if session_id:
            return [e for e in self._entries if e.session_id == session_id]
        return list(self._entries)

    def search(self, keyword: str) -> list[JournalEntry]:
        """Search entries by keyword in lesson text."""
        kw = keyword.lower()
        return [e for e in self._entries if kw in e.lesson.lower()]

    def by_category(self, category: str) -> list[JournalEntry]:
        """Filter entries by category."""
        return [e for e in self._entries if e.category == category]

    def by_tag(self, tag: str) -> list[JournalEntry]:
        """Filter entries by tag."""
        return [e for e in self._entries if tag in e.tags]

    def extract_patterns(self) -> list[dict]:
        """Extract recurring patterns from lessons."""
        word_freq: dict[str, int] = {}
        for e in self._entries:
            words = set(e.lesson.lower().split())
            for w in words:
                if len(w) > 4:  # skip short words
                    word_freq[w] = word_freq.get(w, 0) + 1
        # Return words appearing 3+ times
        patterns = [
            {"word": w, "frequency": f}
            for w, f in sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            if f >= 3
        ]
        return patterns[:20]

    def high_impact(self) -> list[JournalEntry]:
        """Get high-impact lessons."""
        return [e for e in self._entries if e.impact == "high"]

    def summary(self) -> dict:
        categories: dict[str, int] = {}
        for e in self._entries:
            categories[e.category] = categories.get(e.category, 0) + 1
        return {
            "total_entries": len(self._entries),
            "categories": categories,
            "high_impact": len(self.high_impact()),
            "sessions": len(set(e.session_id for e in self._entries)),
        }
