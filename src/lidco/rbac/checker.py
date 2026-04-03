"""Permission checker with audit trail — Q259."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from lidco.rbac.roles import RoleRegistry


@dataclass(frozen=True)
class CheckResult:
    """Result of a permission check."""

    allowed: bool
    reason: str
    role: str
    permission: str


class PermissionChecker:
    """Check user permissions against a RoleRegistry. Deny-by-default."""

    def __init__(self, registry: RoleRegistry) -> None:
        self._registry = registry
        self._user_roles: dict[str, str] = {}
        self._history: deque[CheckResult] = deque(maxlen=10000)

    def assign_role(self, user: str, role_name: str) -> bool:
        """Assign a role to a user. Returns False if role doesn't exist."""
        if self._registry.get(role_name) is None:
            return False
        self._user_roles[user] = role_name
        return True

    def get_role(self, user: str) -> str:
        """Get the role assigned to a user, defaulting to 'viewer'."""
        return self._user_roles.get(user, "viewer")

    def check(self, user: str, permission: str) -> CheckResult:
        """Check if user has the given permission. Deny-by-default."""
        role_name = self.get_role(user)
        allowed = self._registry.has_permission(role_name, permission)
        reason = "granted" if allowed else "denied: insufficient permissions"
        result = CheckResult(
            allowed=allowed,
            reason=reason,
            role=role_name,
            permission=permission,
        )
        self._history.append(result)
        return result

    def check_tool(self, user: str, tool_name: str) -> CheckResult:
        """Check tool usage permission."""
        return self.check(user, "tool.use")

    def check_file(self, user: str, file_path: str) -> CheckResult:
        """Check file access permission."""
        return self.check(user, "file.read")

    def check_command(self, user: str, command: str) -> CheckResult:
        """Check command execution permission."""
        return self.check(user, "command.execute")

    def history(self, user: str | None = None, limit: int = 100) -> list[CheckResult]:
        """Return check history, optionally filtered by user."""
        items = list(self._history)
        if user is not None:
            # Filter by checking if the role matches what's assigned to that user
            # Since CheckResult stores role, we filter on role matching
            role = self.get_role(user)
            items = [r for r in items if r.role == role]
        return items[-limit:]

    def summary(self) -> dict:
        """Return summary statistics."""
        total = len(self._history)
        allowed = sum(1 for r in self._history if r.allowed)
        return {
            "total_checks": total,
            "allowed": allowed,
            "denied": total - allowed,
            "users": len(self._user_roles),
        }
