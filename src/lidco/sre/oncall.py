"""On-Call Manager — schedules, rotation, escalation, overrides, fatigue tracking, handoff notes.

Stdlib only.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OnCallError(Exception):
    """Raised when an on-call operation fails."""


class EscalationLevel(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    MANAGER = "manager"
    EXECUTIVE = "executive"


@dataclass
class OnCallPerson:
    """A person who can be on-call."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    email: str = ""
    phone: str = ""
    team: str = ""


@dataclass
class RotationSlot:
    """A single slot in an on-call rotation."""

    person_id: str
    start_epoch: float
    end_epoch: float
    level: EscalationLevel = EscalationLevel.PRIMARY

    def is_active(self, at: float | None = None) -> bool:
        t = at if at is not None else time.time()
        return self.start_epoch <= t < self.end_epoch

    def duration_hours(self) -> float:
        return (self.end_epoch - self.start_epoch) / 3600.0


@dataclass
class Override:
    """A temporary on-call override."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    original_person_id: str = ""
    replacement_person_id: str = ""
    start_epoch: float = 0.0
    end_epoch: float = 0.0
    reason: str = ""

    def is_active(self, at: float | None = None) -> bool:
        t = at if at is not None else time.time()
        return self.start_epoch <= t < self.end_epoch


@dataclass
class EscalationPolicy:
    """Policy for escalating pages."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    levels: list[EscalationLevel] = field(default_factory=lambda: [
        EscalationLevel.PRIMARY, EscalationLevel.SECONDARY, EscalationLevel.MANAGER,
    ])
    timeout_seconds: float = 300.0  # time before escalating to next level


@dataclass
class FatigueRecord:
    """Track on-call fatigue for a person."""

    person_id: str
    hours_on_call: float = 0.0
    incidents_handled: int = 0
    pages_received: int = 0
    last_paged_at: float | None = None

    def fatigue_score(self) -> float:
        """Higher score = more fatigued. 0–100 scale."""
        hour_factor = min(self.hours_on_call / 168.0, 1.0) * 40  # 168h = 1 week
        incident_factor = min(self.incidents_handled / 10.0, 1.0) * 30
        page_factor = min(self.pages_received / 20.0, 1.0) * 30
        return hour_factor + incident_factor + page_factor


@dataclass
class HandoffNote:
    """Notes passed from one on-call to the next."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    from_person_id: str = ""
    to_person_id: str = ""
    content: str = ""
    open_issues: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class OnCallManager:
    """Manage on-call schedules, rotations, escalations, and fatigue."""

    def __init__(self) -> None:
        self._people: dict[str, OnCallPerson] = {}
        self._slots: list[RotationSlot] = []
        self._overrides: list[Override] = []
        self._policies: dict[str, EscalationPolicy] = {}
        self._fatigue: dict[str, FatigueRecord] = {}
        self._handoffs: list[HandoffNote] = []

    # ---- People ----

    def add_person(self, person: OnCallPerson) -> OnCallPerson:
        if not person.name:
            raise OnCallError("Person name is required")
        self._people[person.id] = person
        return person

    def get_person(self, person_id: str) -> OnCallPerson:
        if person_id not in self._people:
            raise OnCallError(f"Person not found: {person_id}")
        return self._people[person_id]

    def list_people(self) -> list[OnCallPerson]:
        return list(self._people.values())

    # ---- Rotation ----

    def add_slot(self, slot: RotationSlot) -> RotationSlot:
        if slot.person_id not in self._people:
            raise OnCallError(f"Person not found: {slot.person_id}")
        if slot.end_epoch <= slot.start_epoch:
            raise OnCallError("Slot end must be after start")
        self._slots.append(slot)
        return slot

    def current_on_call(self, level: EscalationLevel = EscalationLevel.PRIMARY, at: float | None = None) -> OnCallPerson | None:
        """Return who is currently on-call, considering overrides."""
        t = at if at is not None else time.time()

        # Check overrides first
        for ov in self._overrides:
            if ov.is_active(t):
                # Find the slot for original person
                for slot in self._slots:
                    if slot.person_id == ov.original_person_id and slot.level == level and slot.is_active(t):
                        return self._people.get(ov.replacement_person_id)

        # Regular rotation
        for slot in self._slots:
            if slot.level == level and slot.is_active(t):
                return self._people.get(slot.person_id)
        return None

    def list_slots(self, person_id: str | None = None) -> list[RotationSlot]:
        if person_id is None:
            return list(self._slots)
        return [s for s in self._slots if s.person_id == person_id]

    # ---- Overrides ----

    def add_override(self, override: Override) -> Override:
        if override.replacement_person_id not in self._people:
            raise OnCallError(f"Replacement person not found: {override.replacement_person_id}")
        self._overrides.append(override)
        return override

    def list_overrides(self, active_only: bool = False, at: float | None = None) -> list[Override]:
        if not active_only:
            return list(self._overrides)
        return [o for o in self._overrides if o.is_active(at)]

    # ---- Escalation ----

    def add_policy(self, policy: EscalationPolicy) -> EscalationPolicy:
        if not policy.name:
            raise OnCallError("Policy name is required")
        self._policies[policy.id] = policy
        return policy

    def get_policy(self, policy_id: str) -> EscalationPolicy:
        if policy_id not in self._policies:
            raise OnCallError(f"Policy not found: {policy_id}")
        return self._policies[policy_id]

    def escalation_chain(self, policy_id: str, at: float | None = None) -> list[OnCallPerson]:
        """Return the chain of people to escalate through."""
        policy = self.get_policy(policy_id)
        chain: list[OnCallPerson] = []
        for level in policy.levels:
            person = self.current_on_call(level=level, at=at)
            if person is not None:
                chain.append(person)
        return chain

    # ---- Fatigue ----

    def record_fatigue(self, person_id: str, hours: float = 0.0, incidents: int = 0, pages: int = 0) -> FatigueRecord:
        if person_id not in self._people:
            raise OnCallError(f"Person not found: {person_id}")
        if person_id not in self._fatigue:
            self._fatigue[person_id] = FatigueRecord(person_id=person_id)
        rec = self._fatigue[person_id]
        # Immutable update via replacement
        updated = FatigueRecord(
            person_id=rec.person_id,
            hours_on_call=rec.hours_on_call + hours,
            incidents_handled=rec.incidents_handled + incidents,
            pages_received=rec.pages_received + pages,
            last_paged_at=time.time() if pages > 0 else rec.last_paged_at,
        )
        self._fatigue[person_id] = updated
        return updated

    def get_fatigue(self, person_id: str) -> FatigueRecord:
        if person_id not in self._fatigue:
            return FatigueRecord(person_id=person_id)
        return self._fatigue[person_id]

    # ---- Handoff ----

    def create_handoff(self, from_id: str, to_id: str, content: str, open_issues: list[str] | None = None) -> HandoffNote:
        if from_id not in self._people:
            raise OnCallError(f"Person not found: {from_id}")
        if to_id not in self._people:
            raise OnCallError(f"Person not found: {to_id}")
        note = HandoffNote(from_person_id=from_id, to_person_id=to_id, content=content, open_issues=open_issues or [])
        self._handoffs.append(note)
        return note

    def list_handoffs(self, person_id: str | None = None) -> list[HandoffNote]:
        if person_id is None:
            return list(self._handoffs)
        return [h for h in self._handoffs if h.from_person_id == person_id or h.to_person_id == person_id]
