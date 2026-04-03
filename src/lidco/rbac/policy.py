"""Attribute-based policy engine — Q259."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PolicyCondition:
    """A single condition for policy evaluation."""

    attribute: str
    operator: str  # "eq" | "ne" | "in" | "not_in" | "gt" | "lt"
    value: Any


@dataclass
class Policy:
    """A named policy with effect and conditions."""

    name: str
    effect: str  # "allow" | "deny"
    conditions: list[PolicyCondition] = field(default_factory=list)
    priority: int = 0


class PolicyEngine:
    """Evaluate attribute-based policies with caching."""

    def __init__(self, cache_size: int = 256) -> None:
        self._policies: dict[str, Policy] = {}
        self._cache: dict[str, str] = {}
        self._cache_size = cache_size

    def add_policy(self, policy: Policy) -> Policy:
        """Add a policy to the engine."""
        self._policies[policy.name] = policy
        self._cache.clear()
        return policy

    def remove_policy(self, name: str) -> bool:
        """Remove a policy by name."""
        if name in self._policies:
            del self._policies[name]
            self._cache.clear()
            return True
        return False

    def evaluate(self, context: dict) -> str:
        """Evaluate policies against context. Highest priority matching wins. Default deny."""
        cache_key = json.dumps(context, sort_keys=True, default=str)
        if cache_key in self._cache:
            return self._cache[cache_key]

        matching: list[Policy] = []
        for policy in self._policies.values():
            if self._matches(policy, context):
                matching.append(policy)

        if not matching:
            result = "deny"
        else:
            matching.sort(key=lambda p: p.priority, reverse=True)
            result = matching[0].effect

        # Cache management
        if len(self._cache) >= self._cache_size:
            # Evict oldest entry
            first_key = next(iter(self._cache))
            del self._cache[first_key]
        self._cache[cache_key] = result
        return result

    def _matches(self, policy: Policy, context: dict) -> bool:
        """Check if all conditions of a policy match the context."""
        for cond in policy.conditions:
            if not self._match_condition(cond, context):
                return False
        return True

    def _match_condition(self, condition: PolicyCondition, context: dict) -> bool:
        """Evaluate a single condition against the context."""
        actual = context.get(condition.attribute)
        if actual is None:
            return False
        op = condition.operator
        expected = condition.value
        if op == "eq":
            return actual == expected
        if op == "ne":
            return actual != expected
        if op == "in":
            return actual in expected
        if op == "not_in":
            return actual not in expected
        if op == "gt":
            return actual > expected
        if op == "lt":
            return actual < expected
        return False

    def policies(self) -> list[Policy]:
        """Return all registered policies."""
        return list(self._policies.values())

    def clear_cache(self) -> int:
        """Clear the evaluation cache. Returns number of evicted entries."""
        count = len(self._cache)
        self._cache.clear()
        return count

    def summary(self) -> dict:
        """Return summary dict."""
        return {
            "total_policies": len(self._policies),
            "cache_entries": len(self._cache),
            "cache_size": self._cache_size,
        }
