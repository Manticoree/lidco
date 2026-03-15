"""Role-Based Access Control (RBAC) — Task 325.

Defines viewer/editor/admin roles and enforces per-role tool access limits.

Roles (least to most privileged):
  viewer  — read-only: can view files, search, ask questions
  editor  — viewer + write files, run tests, execute safe commands
  admin   — editor + all tools, config changes, unrestricted bash

Usage::

    rbac = RBACManager()
    rbac.set_role("alice", "editor")
    engine = rbac.engine_for("alice")
    allowed = engine.is_allowed(tool_name="bash", args={"command": "rm -rf /"})
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Role definitions
# ---------------------------------------------------------------------------

ROLES = ("viewer", "editor", "admin")
_ROLE_RANK: dict[str, int] = {r: i for i, r in enumerate(ROLES)}

# Tools allowed by role (additive: editor has viewer's + its own)
_ROLE_ALLOWED_TOOLS: dict[str, frozenset[str]] = {
    "viewer": frozenset({
        "read_file", "list_directory", "grep_codebase", "web_search",
        "web_fetch", "search_memory", "get_context",
    }),
    "editor": frozenset({
        "write_file", "edit_file", "bash",    # safe commands only
        "run_tests", "lint", "format",
        "git_status", "git_diff", "git_log",
        "error_report", "analyze_imports",
    }),
    "admin": frozenset({
        # Admin gets everything — represented as wildcard
        "*",
    }),
}

# Bash command patterns that are blocked for non-admin roles
_EDITOR_BLOCKED_BASH = (
    "rm -rf",
    "sudo ",
    "chmod 777",
    "> /dev/",
    "dd if=",
    "mkfs",
    "format ",
    ":(){:|:&};:",   # fork bomb
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AccessDecision:
    """Result of an RBAC access check."""

    allowed: bool
    role: str
    tool_name: str
    reason: str = ""


@dataclass
class UserRole:
    username: str
    role: str
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# RBACEngine — per-user access checks
# ---------------------------------------------------------------------------

class RBACEngine:
    """Checks whether a user with a given role can use a tool.

    Args:
        role: The user's role (viewer/editor/admin).
    """

    def __init__(self, role: str) -> None:
        if role not in ROLES:
            raise ValueError(f"Unknown role '{role}'. Valid: {ROLES}")
        self._role = role
        self._rank = _ROLE_RANK[role]

    @property
    def role(self) -> str:
        return self._role

    def is_allowed(self, tool_name: str, args: dict[str, Any] | None = None) -> AccessDecision:
        """Check if the current role can use *tool_name* with given *args*.

        Args:
            tool_name: Name of the tool being invoked.
            args: Tool arguments (used for bash command inspection).
        """
        if self._role == "admin":
            return AccessDecision(allowed=True, role=self._role, tool_name=tool_name, reason="admin")

        # Collect allowed tools for this role (additive)
        allowed: frozenset[str] = frozenset()
        for rank, role in enumerate(ROLES):
            if rank <= self._rank:
                allowed = allowed | _ROLE_ALLOWED_TOOLS[role]

        if tool_name not in allowed:
            return AccessDecision(
                allowed=False,
                role=self._role,
                tool_name=tool_name,
                reason=f"Role '{self._role}' does not have access to '{tool_name}'",
            )

        # Extra bash command inspection for editor role
        if tool_name == "bash" and self._role == "editor" and args:
            command = str(args.get("command", ""))
            for blocked in _EDITOR_BLOCKED_BASH:
                if blocked in command:
                    return AccessDecision(
                        allowed=False,
                        role=self._role,
                        tool_name=tool_name,
                        reason=f"Command '{blocked}' is blocked for role '{self._role}'",
                    )

        return AccessDecision(allowed=True, role=self._role, tool_name=tool_name)

    def allowed_tools(self) -> frozenset[str]:
        """Return the set of tools this role can use."""
        if self._role == "admin":
            return frozenset({"*"})
        result: frozenset[str] = frozenset()
        for rank, role in enumerate(ROLES):
            if rank <= self._rank:
                result = result | _ROLE_ALLOWED_TOOLS[role]
        return result


# ---------------------------------------------------------------------------
# RBACManager — multi-user registry
# ---------------------------------------------------------------------------

class RBACManager:
    """Manages user→role assignments and vends RBACEngine instances.

    Args:
        default_role: Role assigned to unknown users (default: "viewer").
    """

    def __init__(self, default_role: str = "viewer") -> None:
        if default_role not in ROLES:
            raise ValueError(f"Unknown default role '{default_role}'")
        self._default = default_role
        self._users: dict[str, UserRole] = {}

    def set_role(self, username: str, role: str, tags: list[str] | None = None) -> None:
        """Assign a role to a user."""
        if role not in ROLES:
            raise ValueError(f"Unknown role '{role}'")
        self._users[username] = UserRole(username=username, role=role, tags=list(tags or []))

    def get_role(self, username: str) -> str:
        """Return the role for a user (default if unknown)."""
        return self._users.get(username, UserRole(username=username, role=self._default)).role

    def remove_user(self, username: str) -> bool:
        if username in self._users:
            del self._users[username]
            return True
        return False

    def engine_for(self, username: str) -> RBACEngine:
        """Return an RBACEngine for the given user."""
        role = self.get_role(username)
        return RBACEngine(role)

    def list_users(self) -> list[UserRole]:
        return sorted(self._users.values(), key=lambda u: u.username)
