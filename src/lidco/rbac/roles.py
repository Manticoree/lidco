"""Role registry with permission inheritance — Q259."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Permission:
    """A single permission entry."""

    name: str
    scope: str  # "tool" | "file" | "command" | "all"
    description: str = ""


@dataclass
class Role:
    """A named role with permissions and optional inheritance."""

    name: str
    permissions: list[Permission] = field(default_factory=list)
    inherits: list[str] = field(default_factory=list)
    description: str = ""


# Built-in permissions
_PERM_ALL = Permission("*", "all", "Full access")
_PERM_TOOL_USE = Permission("tool.use", "tool", "Use tools")
_PERM_FILE_READ = Permission("file.read", "file", "Read files")
_PERM_FILE_WRITE = Permission("file.write", "file", "Write files")
_PERM_COMMAND_EXEC = Permission("command.execute", "command", "Execute commands")
_PERM_READ_ONLY = Permission("read", "file", "Read-only access")
_PERM_AUDIT = Permission("audit.view", "command", "View audit logs")

_BUILTIN_ROLES: list[Role] = [
    Role(
        name="admin",
        permissions=[_PERM_ALL],
        description="Full administrative access",
    ),
    Role(
        name="developer",
        permissions=[_PERM_TOOL_USE, _PERM_FILE_READ, _PERM_FILE_WRITE, _PERM_COMMAND_EXEC],
        description="Standard developer access",
    ),
    Role(
        name="viewer",
        permissions=[_PERM_READ_ONLY],
        description="Read-only access",
    ),
    Role(
        name="auditor",
        permissions=[_PERM_READ_ONLY, _PERM_AUDIT],
        inherits=["viewer"],
        description="Read access plus audit logs",
    ),
]

_BUILTIN_NAMES = frozenset(r.name for r in _BUILTIN_ROLES)


class RoleRegistry:
    """Registry of roles with permission resolution."""

    def __init__(self) -> None:
        self._roles: dict[str, Role] = {}
        for role in _BUILTIN_ROLES:
            self._roles[role.name] = Role(
                name=role.name,
                permissions=list(role.permissions),
                inherits=list(role.inherits),
                description=role.description,
            )

    def register(self, role: Role) -> Role:
        """Register a custom role."""
        self._roles[role.name] = role
        return role

    def get(self, name: str) -> Role | None:
        """Get a role by name."""
        return self._roles.get(name)

    def remove(self, name: str) -> bool:
        """Remove a role. Built-in roles cannot be removed."""
        if name in _BUILTIN_NAMES:
            return False
        if name in self._roles:
            del self._roles[name]
            return True
        return False

    def resolve_permissions(self, role_name: str) -> set[str]:
        """Resolve all permission names including inherited ones."""
        visited: set[str] = set()
        perms: set[str] = set()
        self._resolve(role_name, visited, perms)
        return perms

    def _resolve(self, role_name: str, visited: set[str], perms: set[str]) -> None:
        if role_name in visited:
            return
        visited.add(role_name)
        role = self._roles.get(role_name)
        if role is None:
            return
        for p in role.permissions:
            perms.add(p.name)
        for parent in role.inherits:
            self._resolve(parent, visited, perms)

    def all_roles(self) -> list[Role]:
        """Return all registered roles."""
        return list(self._roles.values())

    def has_permission(self, role_name: str, permission_name: str) -> bool:
        """Check if a role has a specific permission (including inherited)."""
        resolved = self.resolve_permissions(role_name)
        return permission_name in resolved or "*" in resolved

    def summary(self) -> dict:
        """Return a summary dict."""
        return {
            "total_roles": len(self._roles),
            "builtin": sorted(_BUILTIN_NAMES),
            "custom": sorted(n for n in self._roles if n not in _BUILTIN_NAMES),
        }
