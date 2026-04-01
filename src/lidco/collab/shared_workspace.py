"""Room-based shared workspace for team collaboration."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import time


class RoomStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class Participant:
    user_id: str
    name: str
    role: str = "editor"
    joined_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class FileLock:
    file_path: str
    owner: str
    acquired_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ActivityEntry:
    user_id: str
    action: str
    target: str = ""
    timestamp: float = field(default_factory=time.time)


class SharedWorkspace:
    """Room-based shared workspace with file locking and activity tracking."""

    def __init__(self, room_id: str, name: str = "") -> None:
        self.room_id = room_id
        self.name = name or room_id
        self.status = RoomStatus.OPEN
        self._participants: dict[str, Participant] = {}
        self._file_locks: dict[str, FileLock] = {}
        self._activity: list[ActivityEntry] = []

    def add_participant(self, user_id: str, name: str, role: str = "editor") -> Participant:
        participant = Participant(user_id=user_id, name=name, role=role)
        self._participants = {**self._participants, user_id: participant}
        return participant

    def remove_participant(self, user_id: str) -> bool:
        if user_id not in self._participants:
            return False
        self._participants = {k: v for k, v in self._participants.items() if k != user_id}
        self._file_locks = {
            k: v for k, v in self._file_locks.items() if v.owner != user_id
        }
        return True

    def lock_file(self, file_path: str, owner: str) -> FileLock | None:
        existing = self._file_locks.get(file_path)
        if existing is not None and existing.owner != owner:
            return None
        lock = FileLock(file_path=file_path, owner=owner)
        self._file_locks = {**self._file_locks, file_path: lock}
        return lock

    def unlock_file(self, file_path: str, owner: str) -> bool:
        existing = self._file_locks.get(file_path)
        if existing is None or existing.owner != owner:
            return False
        self._file_locks = {
            k: v for k, v in self._file_locks.items() if k != file_path
        }
        return True

    def get_locks(self) -> list[FileLock]:
        return list(self._file_locks.values())

    def detect_conflicts(self, file_path: str, users: list[str]) -> list[str]:
        lock = self._file_locks.get(file_path)
        if lock is None:
            return []
        return [u for u in users if u != lock.owner]

    def get_participants(self) -> list[Participant]:
        return list(self._participants.values())

    def log_activity(self, user_id: str, action: str, target: str = "") -> None:
        entry = ActivityEntry(user_id=user_id, action=action, target=target)
        self._activity = [*self._activity, entry]

    def get_activity(self, limit: int = 50) -> list[ActivityEntry]:
        return self._activity[-limit:]

    def close(self) -> None:
        self.status = RoomStatus.CLOSED

    def summary(self) -> str:
        lines = [
            f"Room: {self.name} ({self.room_id})",
            f"Status: {self.status.value}",
            f"Participants: {len(self._participants)}",
            f"Active locks: {len(self._file_locks)}",
            f"Activity entries: {len(self._activity)}",
        ]
        return "\n".join(lines)
