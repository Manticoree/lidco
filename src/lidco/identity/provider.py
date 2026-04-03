"""IdentityProvider — Abstract identity provider; local backend; user info."""
from __future__ import annotations

import hashlib
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class UserInfo:
    user_id: str
    username: str
    email: str = ""
    groups: list[str] = field(default_factory=list)
    attributes: dict = field(default_factory=dict)


class IdentityProvider(ABC):
    """Abstract identity provider."""

    @abstractmethod
    def authenticate(self, username: str, password: str) -> UserInfo | None:
        """Authenticate and return user info, or None on failure."""

    @abstractmethod
    def get_user(self, user_id: str) -> UserInfo | None:
        """Lookup user by ID."""

    @abstractmethod
    def list_users(self) -> list[UserInfo]:
        """Return all users."""


class LocalIdentityProvider(IdentityProvider):
    """In-memory identity provider with hashed passwords."""

    def __init__(self) -> None:
        self._users: dict[str, UserInfo] = {}
        self._passwords: dict[str, str] = {}  # user_id -> hashed password
        self._username_to_id: dict[str, str] = {}

    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def add_user(
        self,
        username: str,
        password: str,
        email: str = "",
        groups: list[str] | None = None,
    ) -> UserInfo:
        """Add a user. Returns UserInfo."""
        user_id = str(uuid.uuid4())
        info = UserInfo(
            user_id=user_id,
            username=username,
            email=email,
            groups=groups or [],
        )
        self._users[user_id] = info
        self._passwords[user_id] = self._hash_password(password)
        self._username_to_id[username] = user_id
        return info

    def remove_user(self, user_id: str) -> bool:
        """Remove user by ID. Return True if removed."""
        info = self._users.pop(user_id, None)
        if info is None:
            return False
        self._passwords.pop(user_id, None)
        self._username_to_id.pop(info.username, None)
        return True

    def authenticate(self, username: str, password: str) -> UserInfo | None:
        """Authenticate by username and password."""
        uid = self._username_to_id.get(username)
        if uid is None:
            return None
        if self._passwords.get(uid) != self._hash_password(password):
            return None
        return self._users.get(uid)

    def get_user(self, user_id: str) -> UserInfo | None:
        return self._users.get(user_id)

    def list_users(self) -> list[UserInfo]:
        return list(self._users.values())

    def summary(self) -> dict:
        return {
            "total_users": len(self._users),
            "usernames": sorted(self._username_to_id.keys()),
        }
