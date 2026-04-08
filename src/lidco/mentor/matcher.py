"""Mentor Matcher — Match mentors and mentees.

Skill complementarity scoring, availability alignment, interest matching,
and project-based pairing.  Pure stdlib, no external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Skill:
    """A single skill with proficiency level."""

    name: str
    level: int  # 1 (beginner) .. 5 (expert)


@dataclass(frozen=True)
class Availability:
    """Weekly availability window."""

    day: str  # e.g. "monday", "tuesday"
    start_hour: int  # 0..23
    end_hour: int  # 0..23

    def overlaps(self, other: Availability) -> bool:
        """Check if two availability windows overlap on the same day."""
        if self.day.lower() != other.day.lower():
            return False
        return self.start_hour < other.end_hour and other.start_hour < self.end_hour

    def overlap_hours(self, other: Availability) -> int:
        """Return number of overlapping hours, or 0 if none."""
        if not self.overlaps(other):
            return 0
        start = max(self.start_hour, other.start_hour)
        end = min(self.end_hour, other.end_hour)
        return max(0, end - start)


@dataclass
class Profile:
    """Mentor or mentee profile."""

    user_id: str
    name: str
    skills: list[Skill] = field(default_factory=list)
    interests: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    availability: list[Availability] = field(default_factory=list)
    is_mentor: bool = False
    max_mentees: int = 3


@dataclass(frozen=True)
class MatchScore:
    """Result of matching a mentor with a mentee."""

    mentor_id: str
    mentee_id: str
    skill_score: float  # 0.0 .. 1.0
    availability_score: float  # 0.0 .. 1.0
    interest_score: float  # 0.0 .. 1.0
    project_score: float  # 0.0 .. 1.0

    @property
    def total(self) -> float:
        """Weighted total score."""
        return (
            self.skill_score * 0.35
            + self.availability_score * 0.25
            + self.interest_score * 0.20
            + self.project_score * 0.20
        )

    @property
    def label(self) -> str:
        if self.total >= 0.8:
            return "excellent"
        if self.total >= 0.6:
            return "good"
        if self.total >= 0.4:
            return "fair"
        return "poor"


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------

class MentorMatcher:
    """Match mentors with mentees based on multiple criteria."""

    def __init__(self) -> None:
        self._profiles: dict[str, Profile] = {}

    # -- Profile management --------------------------------------------------

    def add_profile(self, profile: Profile) -> None:
        """Add or update a profile."""
        self._profiles[profile.user_id] = profile

    def remove_profile(self, user_id: str) -> bool:
        """Remove a profile. Returns True if found."""
        return self._profiles.pop(user_id, None) is not None

    def get_profile(self, user_id: str) -> Profile | None:
        """Get a profile by user ID."""
        return self._profiles.get(user_id)

    @property
    def profiles(self) -> list[Profile]:
        return list(self._profiles.values())

    @property
    def mentors(self) -> list[Profile]:
        return [p for p in self._profiles.values() if p.is_mentor]

    @property
    def mentees(self) -> list[Profile]:
        return [p for p in self._profiles.values() if not p.is_mentor]

    # -- Scoring -------------------------------------------------------------

    def skill_complementarity(self, mentor: Profile, mentee: Profile) -> float:
        """Score how well mentor skills complement mentee needs.

        Higher score when mentor is strong where mentee is weak.
        """
        if not mentor.skills or not mentee.skills:
            return 0.0

        mentor_map = {s.name.lower(): s.level for s in mentor.skills}
        total = 0.0
        count = 0
        for skill in mentee.skills:
            key = skill.name.lower()
            if key in mentor_map:
                gap = mentor_map[key] - skill.level
                # Positive gap means mentor is more skilled
                total += max(0.0, min(1.0, gap / 4.0))
                count += 1

        if count == 0:
            # Check if mentor has skills mentee doesn't have yet
            mentee_names = {s.name.lower() for s in mentee.skills}
            bonus = sum(
                1 for s in mentor.skills if s.name.lower() not in mentee_names and s.level >= 3
            )
            return min(1.0, bonus * 0.2)

        return total / count

    def availability_overlap(self, mentor: Profile, mentee: Profile) -> float:
        """Score how well schedules align (0..1)."""
        if not mentor.availability or not mentee.availability:
            return 0.0

        total_overlap = 0
        for ma in mentor.availability:
            for me in mentee.availability:
                total_overlap += ma.overlap_hours(me)

        # Normalize: 10+ hours is perfect
        return min(1.0, total_overlap / 10.0)

    def interest_similarity(self, mentor: Profile, mentee: Profile) -> float:
        """Score interest overlap (Jaccard similarity)."""
        if not mentor.interests or not mentee.interests:
            return 0.0

        m_set = {i.lower() for i in mentor.interests}
        e_set = {i.lower() for i in mentee.interests}
        intersection = m_set & e_set
        union = m_set | e_set
        return len(intersection) / len(union) if union else 0.0

    def project_alignment(self, mentor: Profile, mentee: Profile) -> float:
        """Score project overlap."""
        if not mentor.projects or not mentee.projects:
            return 0.0

        m_set = {p.lower() for p in mentor.projects}
        e_set = {p.lower() for p in mentee.projects}
        intersection = m_set & e_set
        union = m_set | e_set
        return len(intersection) / len(union) if union else 0.0

    def score(self, mentor: Profile, mentee: Profile) -> MatchScore:
        """Compute full match score between a mentor and mentee."""
        return MatchScore(
            mentor_id=mentor.user_id,
            mentee_id=mentee.user_id,
            skill_score=self.skill_complementarity(mentor, mentee),
            availability_score=self.availability_overlap(mentor, mentee),
            interest_score=self.interest_similarity(mentor, mentee),
            project_score=self.project_alignment(mentor, mentee),
        )

    # -- Matching ------------------------------------------------------------

    def find_matches(
        self,
        mentee_id: str,
        *,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[MatchScore]:
        """Find best mentor matches for a given mentee."""
        mentee = self._profiles.get(mentee_id)
        if mentee is None or mentee.is_mentor:
            return []

        scores: list[MatchScore] = []
        for mentor in self.mentors:
            ms = self.score(mentor, mentee)
            if ms.total >= min_score:
                scores.append(ms)

        scores.sort(key=lambda s: s.total, reverse=True)
        return scores[:top_k]

    def find_all_matches(self, *, min_score: float = 0.0) -> list[MatchScore]:
        """Find all mentor-mentee matches above threshold."""
        results: list[MatchScore] = []
        for mentee in self.mentees:
            for mentor in self.mentors:
                ms = self.score(mentor, mentee)
                if ms.total >= min_score:
                    results.append(ms)

        results.sort(key=lambda s: s.total, reverse=True)
        return results
