"""Skill Tracker -- track developer skills, language proficiency, framework knowledge, growth."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillEntry:
    """A single skill with proficiency tracking."""

    name: str
    category: str  # "language", "framework", "tool", "concept"
    proficiency: float = 0.0  # 0.0 - 1.0
    xp: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)

    def record(self, delta_xp: int, note: str = "") -> None:
        """Record skill usage / practice."""
        self.xp += max(0, delta_xp)
        self.proficiency = min(1.0, self.xp / 1000.0)
        self.history.append(
            {"timestamp": time.time(), "delta_xp": delta_xp, "note": note}
        )

    def level(self) -> str:
        if self.proficiency < 0.2:
            return "beginner"
        if self.proficiency < 0.5:
            return "intermediate"
        if self.proficiency < 0.8:
            return "advanced"
        return "expert"


@dataclass
class SkillSnapshot:
    """Point-in-time snapshot of all skills."""

    timestamp: float
    skills: dict[str, float]  # name -> proficiency


class SkillTracker:
    """Track developer skills and growth over time."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillEntry] = {}
        self._snapshots: list[SkillSnapshot] = []

    # -- core API --------------------------------------------------------

    def add_skill(self, name: str, category: str = "language") -> SkillEntry:
        if name in self._skills:
            return self._skills[name]
        entry = SkillEntry(name=name, category=category)
        self._skills[name] = entry
        return entry

    def record_usage(self, name: str, delta_xp: int = 10, note: str = "") -> SkillEntry:
        entry = self._skills.get(name)
        if entry is None:
            entry = self.add_skill(name)
        entry.record(delta_xp, note)
        return entry

    def get_skill(self, name: str) -> SkillEntry | None:
        return self._skills.get(name)

    def list_skills(self, category: str | None = None) -> list[SkillEntry]:
        skills = list(self._skills.values())
        if category:
            skills = [s for s in skills if s.category == category]
        return sorted(skills, key=lambda s: -s.proficiency)

    def snapshot(self) -> SkillSnapshot:
        snap = SkillSnapshot(
            timestamp=time.time(),
            skills={n: e.proficiency for n, e in self._skills.items()},
        )
        self._snapshots.append(snap)
        return snap

    @property
    def snapshots(self) -> list[SkillSnapshot]:
        return list(self._snapshots)

    def growth(self, name: str) -> list[dict[str, Any]]:
        """Return growth timeline for a skill from snapshots."""
        return [
            {"timestamp": s.timestamp, "proficiency": s.skills.get(name, 0.0)}
            for s in self._snapshots
            if name in s.skills
        ]

    def top_skills(self, n: int = 5) -> list[SkillEntry]:
        return self.list_skills()[:n]

    def weak_skills(self, threshold: float = 0.3) -> list[SkillEntry]:
        return [s for s in self._skills.values() if s.proficiency < threshold]

    def format_summary(self) -> str:
        if not self._skills:
            return "No skills tracked."
        lines = [f"Skills ({len(self._skills)}):"]
        for entry in self.list_skills():
            lines.append(
                f"  {entry.name} [{entry.category}] "
                f"proficiency={entry.proficiency:.0%} level={entry.level()} xp={entry.xp}"
            )
        return "\n".join(lines)
