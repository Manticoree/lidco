"""UserDirectory — User/group management; group-based permissions; profile storage."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class UserProfile:
    user_id: str
    username: str
    email: str = ""
    display_name: str = ""
    groups: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    active: bool = True


@dataclass
class Group:
    name: str
    description: str = ""
    members: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)


class UserDirectory:
    """User and group management with group-based permissions."""

    def __init__(self) -> None:
        self._users: dict[str, UserProfile] = {}
        self._username_to_id: dict[str, str] = {}
        self._groups: dict[str, Group] = {}

    def add_user(
        self, username: str, email: str = "", display_name: str = ""
    ) -> UserProfile:
        """Add a user profile."""
        user_id = str(uuid.uuid4())
        profile = UserProfile(
            user_id=user_id,
            username=username,
            email=email,
            display_name=display_name,
        )
        self._users[user_id] = profile
        self._username_to_id[username] = user_id
        return profile

    def get_user(self, user_id: str) -> UserProfile | None:
        return self._users.get(user_id)

    def find_by_username(self, username: str) -> UserProfile | None:
        uid = self._username_to_id.get(username)
        if uid is None:
            return None
        return self._users.get(uid)

    def remove_user(self, user_id: str) -> bool:
        """Remove a user and their group memberships."""
        profile = self._users.pop(user_id, None)
        if profile is None:
            return False
        self._username_to_id.pop(profile.username, None)
        # Remove from all groups
        for group in self._groups.values():
            if user_id in group.members:
                group.members.remove(user_id)
        return True

    def create_group(
        self, name: str, description: str = "", permissions: list[str] | None = None
    ) -> Group:
        """Create a group."""
        group = Group(
            name=name,
            description=description,
            permissions=permissions or [],
        )
        self._groups[name] = group
        return group

    def add_to_group(self, user_id: str, group_name: str) -> bool:
        """Add user to group. Return True on success."""
        group = self._groups.get(group_name)
        if group is None:
            return False
        if user_id not in self._users:
            return False
        if user_id in group.members:
            return True
        group.members.append(user_id)
        user = self._users[user_id]
        if group_name not in user.groups:
            user.groups.append(group_name)
        return True

    def remove_from_group(self, user_id: str, group_name: str) -> bool:
        """Remove user from group. Return True on success."""
        group = self._groups.get(group_name)
        if group is None:
            return False
        if user_id not in group.members:
            return False
        group.members.remove(user_id)
        user = self._users.get(user_id)
        if user and group_name in user.groups:
            user.groups.remove(group_name)
        return True

    def user_permissions(self, user_id: str) -> set[str]:
        """Return union of all group permissions for a user."""
        user = self._users.get(user_id)
        if user is None:
            return set()
        perms: set[str] = set()
        for gname in user.groups:
            group = self._groups.get(gname)
            if group:
                perms.update(group.permissions)
        return perms

    def group_members(self, group_name: str) -> list[UserProfile]:
        """Return profiles of all members in a group."""
        group = self._groups.get(group_name)
        if group is None:
            return []
        return [self._users[uid] for uid in group.members if uid in self._users]

    def all_users(self, include_inactive: bool = False) -> list[UserProfile]:
        """Return all users, optionally including inactive."""
        if include_inactive:
            return list(self._users.values())
        return [u for u in self._users.values() if u.active]

    def all_groups(self) -> list[Group]:
        return list(self._groups.values())

    def summary(self) -> dict:
        return {
            "total_users": len(self._users),
            "active_users": len([u for u in self._users.values() if u.active]),
            "total_groups": len(self._groups),
        }
