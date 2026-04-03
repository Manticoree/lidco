"""Data retention policies with legal hold and audit trail."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field


@dataclass
class RetentionPolicy:
    """A data retention policy."""

    name: str
    resource_pattern: str
    retention_days: int
    action: str  # "delete" or "archive"
    legal_hold: bool = False


@dataclass(frozen=True)
class RetentionRecord:
    """Record of a retention action evaluated or executed."""

    resource: str
    policy_name: str
    action: str
    timestamp: float
    held: bool = False


class RetentionManager:
    """Manage data retention policies, legal holds, and audit trails."""

    def __init__(self) -> None:
        self._policies: dict[str, RetentionPolicy] = {}
        self._audit: list[RetentionRecord] = []

    # ------------------------------------------------------------------
    # Policy management
    # ------------------------------------------------------------------

    def add_policy(self, policy: RetentionPolicy) -> RetentionPolicy:
        """Add or replace a retention policy."""
        self._policies[policy.name] = policy
        return policy

    def remove_policy(self, name: str) -> bool:
        """Remove a policy by name. Returns True if removed."""
        return self._policies.pop(name, None) is not None

    def set_legal_hold(self, name: str, held: bool) -> RetentionPolicy | None:
        """Toggle legal hold on a policy. Returns updated policy or None."""
        policy = self._policies.get(name)
        if policy is None:
            return None
        policy.legal_hold = held
        return policy

    def policies(self) -> list[RetentionPolicy]:
        """Return all policies."""
        return list(self._policies.values())

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, resource: str, age_days: float) -> RetentionRecord | None:
        """Evaluate a resource against policies. Returns record or None."""
        for policy in self._policies.values():
            if re.search(policy.resource_pattern, resource):
                if age_days >= policy.retention_days:
                    held = policy.legal_hold
                    record = RetentionRecord(
                        resource=resource,
                        policy_name=policy.name,
                        action="hold" if held else policy.action,
                        timestamp=time.time(),
                        held=held,
                    )
                    self._audit.append(record)
                    return record
        return None

    def pending_actions(
        self, resources: list[tuple[str, float]]
    ) -> list[RetentionRecord]:
        """Evaluate a batch of (resource, age_days) pairs."""
        results: list[RetentionRecord] = []
        for resource, age_days in resources:
            record = self.evaluate(resource, age_days)
            if record is not None:
                results.append(record)
        return results

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def audit_trail(self) -> list[RetentionRecord]:
        """Return all evaluation records."""
        return list(self._audit)

    def summary(self) -> dict:
        """Return summary of retention state."""
        return {
            "policy_count": len(self._policies),
            "audit_count": len(self._audit),
            "policies": [p.name for p in self._policies.values()],
            "held_count": sum(1 for p in self._policies.values() if p.legal_hold),
        }
