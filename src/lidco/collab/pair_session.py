"""Pair programming session management with driver/navigator roles."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import time


class SessionRole(str, Enum):
    DRIVER = "driver"
    NAVIGATOR = "navigator"
    OBSERVER = "observer"


@dataclass(frozen=True)
class PairMember:
    user_id: str
    name: str
    role: SessionRole = SessionRole.NAVIGATOR
    joined_at: float = field(default_factory=time.time)


class PairSession:
    """Pair programming session with driver/navigator role management."""

    def __init__(self, session_id: str, creator: str) -> None:
        self.session_id = session_id
        self._members: dict[str, PairMember] = {}
        self.created_at: float = time.time()
        self._turn_history: list[dict] = []
        self.active: bool = True
        # Creator joins as driver
        self.join(creator, creator, SessionRole.DRIVER)

    def join(
        self,
        user_id: str,
        name: str,
        role: SessionRole = SessionRole.NAVIGATOR,
    ) -> PairMember:
        member = PairMember(user_id=user_id, name=name, role=role)
        self._members = {**self._members, user_id: member}
        return member

    def leave(self, user_id: str) -> bool:
        if user_id not in self._members:
            return False
        self._members = {k: v for k, v in self._members.items() if k != user_id}
        return True

    def swap_roles(self) -> None:
        new_members: dict[str, PairMember] = {}
        for uid, m in self._members.items():
            if m.role == SessionRole.DRIVER:
                new_role = SessionRole.NAVIGATOR
            elif m.role == SessionRole.NAVIGATOR:
                new_role = SessionRole.DRIVER
            else:
                new_role = m.role
            new_members[uid] = PairMember(
                user_id=m.user_id,
                name=m.name,
                role=new_role,
                joined_at=m.joined_at,
            )
        self._members = new_members

    def set_driver(self, user_id: str) -> bool:
        if user_id not in self._members:
            return False
        new_members: dict[str, PairMember] = {}
        for uid, m in self._members.items():
            if uid == user_id:
                new_role = SessionRole.DRIVER
            elif m.role == SessionRole.DRIVER:
                new_role = SessionRole.NAVIGATOR
            else:
                new_role = m.role
            new_members[uid] = PairMember(
                user_id=m.user_id,
                name=m.name,
                role=new_role,
                joined_at=m.joined_at,
            )
        self._members = new_members
        return True

    def get_driver(self) -> PairMember | None:
        for m in self._members.values():
            if m.role == SessionRole.DRIVER:
                return m
        return None

    def get_members(self) -> list[PairMember]:
        return list(self._members.values())

    def record_turn(self, user_id: str, action: str) -> None:
        entry = {"user_id": user_id, "action": action, "timestamp": time.time()}
        self._turn_history = [*self._turn_history, entry]

    def get_turn_history(self, limit: int = 20) -> list[dict]:
        return self._turn_history[-limit:]

    def end(self) -> None:
        self.active = False

    def summary(self) -> str:
        driver = self.get_driver()
        driver_name = driver.name if driver else "none"
        lines = [
            f"Session: {self.session_id}",
            f"Active: {self.active}",
            f"Members: {len(self._members)}",
            f"Driver: {driver_name}",
            f"Turns: {len(self._turn_history)}",
        ]
        return "\n".join(lines)
