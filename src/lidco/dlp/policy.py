"""DLP policy manager — per-project rules, severity, exceptions."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class DLPPolicy:
    """A named DLP policy with rules and exceptions."""

    name: str
    rules: list[str] = field(default_factory=list)
    severity: str = "high"
    exceptions: list[str] = field(default_factory=list)
    enabled: bool = True


@dataclass(frozen=True)
class PolicyEvaluation:
    """Evaluation result for a single policy against content."""

    policy_name: str
    matched: bool
    severity: str
    exception_applied: bool = False


class DLPPolicyManager:
    """Manage and evaluate DLP policies."""

    def __init__(self) -> None:
        self._policies: dict[str, DLPPolicy] = {}

    # ------------------------------------------------------------------

    def add_policy(self, policy: DLPPolicy) -> DLPPolicy:
        self._policies[policy.name] = policy
        return policy

    def remove_policy(self, name: str) -> bool:
        return self._policies.pop(name, None) is not None

    def enable(self, name: str) -> bool:
        pol = self._policies.get(name)
        if pol is None:
            return False
        pol.enabled = True
        return True

    def disable(self, name: str) -> bool:
        pol = self._policies.get(name)
        if pol is None:
            return False
        pol.enabled = False
        return True

    def evaluate(self, content: str, context: str = "") -> list[PolicyEvaluation]:
        """Evaluate all enabled policies against *content*."""
        results: list[PolicyEvaluation] = []
        combined = content + " " + context if context else content
        for pol in self._policies.values():
            if not pol.enabled:
                continue
            matched = any(re.search(r, combined) for r in pol.rules)
            exception_applied = False
            if matched and pol.exceptions:
                if any(re.search(ex, combined) for ex in pol.exceptions):
                    matched = False
                    exception_applied = True
            results.append(
                PolicyEvaluation(
                    policy_name=pol.name,
                    matched=matched,
                    severity=pol.severity,
                    exception_applied=exception_applied,
                )
            )
        return results

    def add_exception(self, policy_name: str, pattern: str) -> bool:
        pol = self._policies.get(policy_name)
        if pol is None:
            return False
        pol.exceptions.append(pattern)
        return True

    def policies(self, enabled_only: bool = False) -> list[DLPPolicy]:
        pols = list(self._policies.values())
        if enabled_only:
            pols = [p for p in pols if p.enabled]
        return pols

    def summary(self) -> dict:
        return {
            "total": len(self._policies),
            "enabled": sum(1 for p in self._policies.values() if p.enabled),
            "disabled": sum(1 for p in self._policies.values() if not p.enabled),
        }
