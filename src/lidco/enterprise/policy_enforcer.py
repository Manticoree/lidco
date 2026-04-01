"""Enforce organization policies."""
from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Any


class PolicyAction(str, enum.Enum):
    """Action to take when a policy matches."""

    ALLOW = "allow"
    DENY = "deny"
    WARN = "warn"
    AUDIT = "audit"


@dataclass(frozen=True)
class Policy:
    """A single policy rule."""

    name: str
    resource: str
    action: PolicyAction
    reason: str = ""
    priority: int = 0


@dataclass(frozen=True)
class PolicyViolation:
    """Record of a policy check that produced a non-ALLOW result."""

    policy_name: str
    resource: str
    action: PolicyAction
    reason: str
    timestamp: float


class PolicyEnforcer:
    """Evaluate resources against a set of policies."""

    def __init__(self) -> None:
        self._policies: dict[str, Policy] = {}
        self._violations: list[PolicyViolation] = []

    def add_policy(self, policy: Policy) -> None:
        """Register a policy."""
        self._policies[policy.name] = policy

    def remove_policy(self, name: str) -> bool:
        """Remove a policy by name. Returns True if it existed."""
        return self._policies.pop(name, None) is not None

    def check(self, resource: str) -> PolicyAction:
        """Return the highest-priority action for *resource*."""
        action, _ = self.check_with_violations(resource)
        return action

    def check_with_violations(self, resource: str) -> tuple[PolicyAction, list[PolicyViolation]]:
        """Check resource and return (action, violations)."""
        matching = [p for p in self._policies.values() if self._matches(p.resource, resource)]
        if not matching:
            return PolicyAction.ALLOW, []

        matching.sort(key=lambda p: p.priority, reverse=True)
        top = matching[0]

        violations: list[PolicyViolation] = []
        for p in matching:
            if p.action != PolicyAction.ALLOW:
                v = PolicyViolation(
                    policy_name=p.name,
                    resource=resource,
                    action=p.action,
                    reason=p.reason,
                    timestamp=time.time(),
                )
                violations.append(v)
                self._violations.append(v)

        return top.action, violations

    def list_policies(self) -> list[Policy]:
        """Return all registered policies."""
        return list(self._policies.values())

    def violations(self) -> list[PolicyViolation]:
        """Return all recorded violations."""
        return list(self._violations)

    def clear_violations(self) -> int:
        """Clear violations and return count cleared."""
        count = len(self._violations)
        self._violations = []
        return count

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [f"PolicyEnforcer: {len(self._policies)} policies, {len(self._violations)} violations"]
        for p in self._policies.values():
            lines.append(f"  {p.name}: {p.resource} -> {p.action.value} (priority={p.priority})")
        return "\n".join(lines)

    @staticmethod
    def _matches(pattern: str, resource: str) -> bool:
        """Check if resource matches pattern. Supports * wildcard and exact match."""
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return resource.startswith(pattern[:-1])
        return pattern == resource
