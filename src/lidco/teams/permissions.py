"""Team permissions — per-team tool allow/deny with inheritance."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionRule:
    """A single permission rule for a tool."""

    tool_name: str
    allowed: bool = True
    scope: str = "team"


class TeamPermissions:
    """Manages allow/deny rules for tools within a team."""

    def __init__(self, team_id: str) -> None:
        self.team_id = team_id
        self._rules: dict[str, PermissionRule] = {}

    def allow(self, tool_name: str) -> None:
        """Allow a tool."""
        self._rules[tool_name] = PermissionRule(tool_name=tool_name, allowed=True)

    def deny(self, tool_name: str) -> None:
        """Deny a tool."""
        self._rules[tool_name] = PermissionRule(tool_name=tool_name, allowed=False)

    def is_allowed(self, tool_name: str, parent_permissions: TeamPermissions | None = None) -> bool:
        """Check if a tool is allowed, falling back to *parent_permissions* if unset."""
        rule = self._rules.get(tool_name)
        if rule is not None:
            return rule.allowed
        if parent_permissions is not None:
            parent_rule = parent_permissions._rules.get(tool_name)
            if parent_rule is not None:
                return parent_rule.allowed
        # Default: allowed
        return True

    def list_rules(self) -> list[PermissionRule]:
        """Return all rules."""
        return list(self._rules.values())

    def clear(self) -> None:
        """Remove all rules."""
        self._rules.clear()

    def merge(self, other: TeamPermissions) -> TeamPermissions:
        """Return a new TeamPermissions merging self with *other* (other wins on conflict)."""
        merged = TeamPermissions(team_id=self.team_id)
        merged._rules = dict(self._rules)
        merged._rules.update(other._rules)
        return merged
