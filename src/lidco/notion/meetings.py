"""MeetingNotes — create and manage meeting notes with action items."""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class ActionItem:
    """An action item extracted from meeting notes."""

    text: str
    assignee: str | None = None
    done: bool = False


@dataclass
class Meeting:
    """A meeting record."""

    id: str
    title: str
    attendees: list[str] = field(default_factory=list)
    notes: str = ""
    action_items: list[ActionItem] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class MeetingNotes:
    """Manage meeting notes with action-item extraction and follow-up assignment."""

    def __init__(self) -> None:
        self._meetings: dict[str, Meeting] = {}

    # ------------------------------------------------------------- CRUD

    def create(self, title: str, attendees: list[str] | None = None) -> Meeting:
        """Create a new meeting.

        Raises
        ------
        ValueError
            If *title* is empty.
        """
        if not title.strip():
            raise ValueError("Title must not be empty")
        meeting_id = uuid.uuid4().hex[:12]
        meeting = Meeting(
            id=meeting_id,
            title=title,
            attendees=list(attendees) if attendees else [],
        )
        self._meetings[meeting_id] = meeting
        return meeting

    def get(self, meeting_id: str) -> Meeting:
        """Get a meeting by ID.

        Raises
        ------
        KeyError
            If the meeting does not exist.
        """
        if meeting_id not in self._meetings:
            raise KeyError(f"Meeting not found: {meeting_id}")
        return self._meetings[meeting_id]

    def add_notes(self, meeting_id: str, text: str) -> None:
        """Append notes to a meeting.

        Raises
        ------
        KeyError
            If the meeting does not exist.
        """
        old = self.get(meeting_id)
        separator = "\n" if old.notes else ""
        self._meetings[meeting_id] = Meeting(
            id=old.id,
            title=old.title,
            attendees=old.attendees,
            notes=old.notes + separator + text,
            action_items=old.action_items,
            created_at=old.created_at,
        )

    # --------------------------------------------------- action items

    def extract_action_items(self, meeting_id: str) -> list[ActionItem]:
        """Extract action items from meeting notes.

        Patterns recognised:
        - Lines starting with ``- [ ]`` or ``- TODO``
        - Lines containing ``ACTION:``

        Raises
        ------
        KeyError
            If the meeting does not exist.
        """
        meeting = self.get(meeting_id)
        items: list[ActionItem] = []
        for line in meeting.notes.splitlines():
            stripped = line.strip()
            if re.match(r"^-\s*\[\s*\]", stripped):
                text = re.sub(r"^-\s*\[\s*\]\s*", "", stripped)
                items.append(ActionItem(text=text))
            elif stripped.upper().startswith("- TODO"):
                text = re.sub(r"^-\s*TODO\s*:?\s*", "", stripped, flags=re.IGNORECASE)
                items.append(ActionItem(text=text))
            elif "ACTION:" in stripped.upper():
                text = re.split(r"ACTION:\s*", stripped, flags=re.IGNORECASE)[-1]
                items.append(ActionItem(text=text))

        # Store extracted items on the meeting
        self._meetings[meeting_id] = Meeting(
            id=meeting.id,
            title=meeting.title,
            attendees=meeting.attendees,
            notes=meeting.notes,
            action_items=items,
            created_at=meeting.created_at,
        )
        return items

    def assign_followup(self, meeting_id: str, item_text: str, person: str) -> bool:
        """Assign a follow-up person to an action item.

        Returns ``True`` if the item was found and assigned, ``False`` otherwise.

        Raises
        ------
        KeyError
            If the meeting does not exist.
        """
        meeting = self.get(meeting_id)
        found = False
        new_items: list[ActionItem] = []
        for ai in meeting.action_items:
            if ai.text == item_text and not found:
                new_items.append(ActionItem(text=ai.text, assignee=person, done=ai.done))
                found = True
            else:
                new_items.append(ai)
        if found:
            self._meetings[meeting_id] = Meeting(
                id=meeting.id,
                title=meeting.title,
                attendees=meeting.attendees,
                notes=meeting.notes,
                action_items=new_items,
                created_at=meeting.created_at,
            )
        return found

    def list_meetings(self) -> list[Meeting]:
        """Return all meetings, newest first."""
        return sorted(self._meetings.values(), key=lambda m: m.created_at, reverse=True)
