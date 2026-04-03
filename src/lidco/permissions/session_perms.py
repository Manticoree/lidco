"""Per-session permission overrides — sticky decisions, reset, export."""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionDecision:
    """A recorded permission decision."""

    scope: str
    resource: str
    action: str
    sticky: bool = False
    decided_at: float = 0.0


class SessionPermissions:
    """Per-session permission overrides with sticky decisions."""

    def __init__(self) -> None:
        self._decisions: dict[tuple[str, str], PermissionDecision] = {}

    def set(
        self,
        scope: str,
        resource: str,
        action: str,
        sticky: bool = False,
    ) -> PermissionDecision:
        """Set a permission decision for *scope*/*resource*."""
        decision = PermissionDecision(
            scope=scope,
            resource=resource,
            action=action,
            sticky=sticky,
            decided_at=time.time(),
        )
        self._decisions[(scope, resource)] = decision
        return decision

    def get(self, scope: str, resource: str) -> PermissionDecision | None:
        """Get the decision for *scope*/*resource*, or None."""
        return self._decisions.get((scope, resource))

    def check(self, scope: str, resource: str) -> str | None:
        """Return the action string for *scope*/*resource*, or None."""
        decision = self._decisions.get((scope, resource))
        if decision is not None:
            return decision.action
        return None

    def reset(self) -> int:
        """Clear non-sticky decisions. Returns count removed."""
        to_remove = [
            k for k, d in self._decisions.items() if not d.sticky
        ]
        for k in to_remove:
            del self._decisions[k]
        return len(to_remove)

    def reset_all(self) -> int:
        """Clear all decisions. Returns count removed."""
        count = len(self._decisions)
        self._decisions.clear()
        return count

    def export(self) -> list[dict]:
        """Export all decisions as a list of dicts."""
        return [
            {
                "scope": d.scope,
                "resource": d.resource,
                "action": d.action,
                "sticky": d.sticky,
                "decided_at": d.decided_at,
            }
            for d in self._decisions.values()
        ]

    def decisions(self) -> list[PermissionDecision]:
        """Return all decisions."""
        return list(self._decisions.values())
