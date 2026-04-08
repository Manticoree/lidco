"""Progress Dashboard -- learning progress, exercises, skill growth, streaks, achievements."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Achievement:
    """An unlockable achievement."""

    name: str
    description: str
    unlocked: bool = False
    unlocked_at: float = 0.0

    def unlock(self) -> Achievement:
        if self.unlocked:
            return self
        return Achievement(
            name=self.name,
            description=self.description,
            unlocked=True,
            unlocked_at=time.time(),
        )


@dataclass
class DailyEntry:
    """A single day of learning activity."""

    date: str  # YYYY-MM-DD
    exercises_completed: int = 0
    xp_earned: int = 0


class ProgressDashboard:
    """Track learning progress, streaks, and achievements."""

    def __init__(self) -> None:
        self._daily: dict[str, DailyEntry] = {}
        self._achievements: dict[str, Achievement] = {}
        self._total_xp: int = 0
        self._exercises_completed: int = 0

    # -- achievements ---------------------------------------------------

    def register_achievement(self, name: str, description: str) -> None:
        if name not in self._achievements:
            self._achievements[name] = Achievement(name=name, description=description)

    def unlock_achievement(self, name: str) -> Achievement | None:
        ach = self._achievements.get(name)
        if ach is None:
            return None
        unlocked = ach.unlock()
        self._achievements[name] = unlocked
        return unlocked

    def list_achievements(self, unlocked_only: bool = False) -> list[Achievement]:
        achs = list(self._achievements.values())
        if unlocked_only:
            achs = [a for a in achs if a.unlocked]
        return sorted(achs, key=lambda a: a.name)

    # -- daily tracking ------------------------------------------------

    def record_day(self, date: str, exercises: int = 0, xp: int = 0) -> DailyEntry:
        entry = self._daily.get(date)
        if entry is None:
            entry = DailyEntry(date=date)
            self._daily[date] = entry
        new_entry = DailyEntry(
            date=date,
            exercises_completed=entry.exercises_completed + exercises,
            xp_earned=entry.xp_earned + xp,
        )
        self._daily[date] = new_entry
        self._total_xp += xp
        self._exercises_completed += exercises
        return new_entry

    def get_day(self, date: str) -> DailyEntry | None:
        return self._daily.get(date)

    # -- streaks -------------------------------------------------------

    def streak(self, dates: list[str]) -> int:
        """Calculate consecutive-day streak from sorted date strings."""
        if not dates:
            return 0
        active_dates = sorted(d for d in dates if d in self._daily)
        if not active_dates:
            return 0
        streak = 1
        max_streak = 1
        for i in range(1, len(active_dates)):
            prev = active_dates[i - 1]
            curr = active_dates[i]
            # Simple consecutive check: dates must be sequential strings
            if _next_date(prev) == curr:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 1
        return max_streak

    # -- summary -------------------------------------------------------

    @property
    def total_xp(self) -> int:
        return self._total_xp

    @property
    def exercises_completed(self) -> int:
        return self._exercises_completed

    def stats(self) -> dict[str, Any]:
        return {
            "total_xp": self._total_xp,
            "exercises_completed": self._exercises_completed,
            "days_active": len(self._daily),
            "achievements_unlocked": sum(1 for a in self._achievements.values() if a.unlocked),
            "achievements_total": len(self._achievements),
        }

    def format_summary(self) -> str:
        s = self.stats()
        lines = [
            f"Total XP: {s['total_xp']}",
            f"Exercises completed: {s['exercises_completed']}",
            f"Days active: {s['days_active']}",
            f"Achievements: {s['achievements_unlocked']}/{s['achievements_total']}",
        ]
        return "\n".join(lines)


def _next_date(date_str: str) -> str:
    """Return next calendar date string (YYYY-MM-DD) after *date_str*."""
    parts = date_str.split("-")
    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    d += 1
    days_in_month = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if (y % 4 == 0 and y % 100 != 0) or y % 400 == 0:
        days_in_month[2] = 29
    if d > days_in_month[m]:
        d = 1
        m += 1
        if m > 12:
            m = 1
            y += 1
    return f"{y:04d}-{m:02d}-{d:02d}"
