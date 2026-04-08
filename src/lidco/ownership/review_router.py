"""
Review Router — route code reviews to appropriate owners.

Load balancing, vacation handling, escalation, round-robin within teams.
Pure stdlib, no external dependencies.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Reviewer:
    """A potential reviewer."""

    name: str
    team: str
    is_available: bool = True
    current_load: int = 0


@dataclass(frozen=True)
class ReviewAssignment:
    """A review routed to one or more reviewers."""

    file_pattern: str
    reviewers: list[str]
    reason: str


@dataclass(frozen=True)
class EscalationResult:
    """Result of an escalation attempt."""

    original_reviewer: str
    escalated_to: str
    reason: str


@dataclass
class RoutingResult:
    """Aggregate result from the review router."""

    assignments: list[ReviewAssignment] = field(default_factory=list)
    escalations: list[EscalationResult] = field(default_factory=list)
    unassigned: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "assigned_count": len(self.assignments),
            "escalation_count": len(self.escalations),
            "unassigned_count": len(self.unassigned),
        }


class ReviewRouter:
    """Route reviews to owners with load balancing and escalation."""

    def __init__(self) -> None:
        self._reviewers: dict[str, Reviewer] = {}
        self._team_members: dict[str, list[str]] = {}
        self._ownership_map: dict[str, list[str]] = {}
        self._round_robin_idx: dict[str, int] = {}
        self._vacation_set: set[str] = set()
        self._escalation_map: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Configuration (immutable-style: return new instances)
    # ------------------------------------------------------------------

    def add_reviewer(self, reviewer: Reviewer) -> ReviewRouter:
        """Add a reviewer. Returns a new router with the reviewer added."""
        new = self._copy()
        new._reviewers = {**self._reviewers, reviewer.name: reviewer}
        members = list(new._team_members.get(reviewer.team, []))
        if reviewer.name not in members:
            members.append(reviewer.name)
        new._team_members = {**self._team_members, reviewer.team: members}
        return new

    def set_ownership(self, pattern: str, owners: list[str]) -> ReviewRouter:
        """Map a file pattern to owner names."""
        new = self._copy()
        new._ownership_map = {**self._ownership_map, pattern: list(owners)}
        return new

    def set_vacation(self, name: str) -> ReviewRouter:
        """Mark a reviewer as on vacation."""
        new = self._copy()
        new._vacation_set = self._vacation_set | {name}
        return new

    def set_escalation(self, source: str, target: str) -> ReviewRouter:
        """Set escalation target for a reviewer."""
        new = self._copy()
        new._escalation_map = {**self._escalation_map, source: target}
        return new

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def route(self, changed_files: list[str]) -> RoutingResult:
        """Route reviews for the given changed files."""
        assignments: list[ReviewAssignment] = []
        escalations: list[EscalationResult] = []
        unassigned: list[str] = []

        for fpath in changed_files:
            owners = self._find_owners(fpath)
            if not owners:
                unassigned.append(fpath)
                continue

            chosen: list[str] = []
            for owner in owners:
                resolved, esc = self._resolve_reviewer(owner)
                if resolved:
                    chosen.append(resolved)
                    if esc:
                        escalations.append(esc)
                # If not resolved, skip (escalation also failed)

            if chosen:
                assignments.append(
                    ReviewAssignment(
                        file_pattern=fpath,
                        reviewers=chosen,
                        reason="ownership match",
                    )
                )
            else:
                unassigned.append(fpath)

        return RoutingResult(
            assignments=assignments,
            escalations=escalations,
            unassigned=unassigned,
        )

    def route_round_robin(self, team: str, count: int = 1) -> list[str]:
        """Pick *count* reviewers from *team* using round-robin."""
        members = self._team_members.get(team, [])
        available = [
            m for m in members
            if m not in self._vacation_set
            and self._reviewers.get(m, Reviewer(name=m, team=team)).is_available
        ]
        if not available:
            return []

        idx = self._round_robin_idx.get(team, 0)
        picked: list[str] = []
        for i in range(count):
            pos = (idx + i) % len(available)
            picked.append(available[pos])
        self._round_robin_idx[team] = (idx + count) % len(available)
        return picked

    def find_least_loaded(self, team: str) -> str | None:
        """Return the reviewer in *team* with the lowest load."""
        members = self._team_members.get(team, [])
        available = [
            self._reviewers[m] for m in members
            if m in self._reviewers
            and m not in self._vacation_set
            and self._reviewers[m].is_available
        ]
        if not available:
            return None
        return min(available, key=lambda r: r.current_load).name

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _find_owners(self, file_path: str) -> list[str]:
        """Match file_path against ownership map patterns."""
        for pattern, owners in self._ownership_map.items():
            if self._pattern_matches(pattern, file_path):
                return owners
        return []

    @staticmethod
    def _pattern_matches(pattern: str, file_path: str) -> bool:
        """Simple prefix / glob-star matching."""
        norm = file_path.replace("\\", "/")
        pat = pattern.replace("\\", "/").rstrip("/")
        if pat == "*":
            return True
        if pat.endswith("/*"):
            return norm.startswith(pat[:-2])
        return norm.startswith(pat) or norm == pat

    def _resolve_reviewer(
        self, owner: str,
    ) -> tuple[str | None, EscalationResult | None]:
        """Resolve an owner to an available reviewer, escalating if needed."""
        if owner not in self._vacation_set:
            rev = self._reviewers.get(owner)
            if rev is None or rev.is_available:
                return owner, None

        # Needs escalation
        target = self._escalation_map.get(owner)
        if target and target not in self._vacation_set:
            return target, EscalationResult(
                original_reviewer=owner,
                escalated_to=target,
                reason="on vacation" if owner in self._vacation_set else "unavailable",
            )
        return None, None

    def _copy(self) -> ReviewRouter:
        r = ReviewRouter()
        r._reviewers = dict(self._reviewers)
        r._team_members = {k: list(v) for k, v in self._team_members.items()}
        r._ownership_map = {k: list(v) for k, v in self._ownership_map.items()}
        r._round_robin_idx = dict(self._round_robin_idx)
        r._vacation_set = set(self._vacation_set)
        r._escalation_map = dict(self._escalation_map)
        return r
