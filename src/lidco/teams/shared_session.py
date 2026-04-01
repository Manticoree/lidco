"""Shared session — multi-user session support with turn-based or concurrent modes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SessionMode(str, Enum):
    """How multiple users interact in a shared session."""

    TURN_BASED = "turn_based"
    CONCURRENT = "concurrent"


@dataclass(frozen=True)
class CursorPosition:
    """A user's cursor location."""

    user_id: str
    file: str
    line: int
    column: int = 0


class SharedSession:
    """A session that multiple users can join."""

    def __init__(self, team_id: str, mode: SessionMode = SessionMode.TURN_BASED) -> None:
        self.team_id = team_id
        self.mode = mode
        self._users: list[str] = []
        self._cursors: dict[str, CursorPosition] = {}
        self._turn_index: int = 0

    def join(self, user_id: str) -> None:
        """Add a user to the session."""
        if user_id not in self._users:
            self._users.append(user_id)

    def leave(self, user_id: str) -> None:
        """Remove a user from the session."""
        if user_id in self._users:
            self._users.remove(user_id)
            self._cursors.pop(user_id, None)
            # Adjust turn index if needed
            if self._turn_index >= len(self._users) and self._users:
                self._turn_index = 0

    def update_cursor(self, user_id: str, file: str, line: int, column: int = 0) -> None:
        """Update cursor position for a user."""
        self._cursors[user_id] = CursorPosition(
            user_id=user_id, file=file, line=line, column=column,
        )

    def get_cursors(self) -> list[CursorPosition]:
        """Return all cursor positions."""
        return list(self._cursors.values())

    def active_users(self) -> list[str]:
        """Return list of active user IDs."""
        return list(self._users)

    def is_turn(self, user_id: str) -> bool:
        """Check if it is *user_id*'s turn (only meaningful in TURN_BASED mode)."""
        if self.mode != SessionMode.TURN_BASED:
            return True
        if not self._users:
            return False
        return self._users[self._turn_index] == user_id

    def next_turn(self) -> str | None:
        """Advance to the next turn. Returns the user whose turn it now is."""
        if not self._users:
            return None
        self._turn_index = (self._turn_index + 1) % len(self._users)
        return self._users[self._turn_index]

    def user_count(self) -> int:
        """Return number of active users."""
        return len(self._users)
