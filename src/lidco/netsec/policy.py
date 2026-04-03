"""Network policy — allowlist/denylist for outbound connections (Q263)."""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyRule:
    """A single network policy rule."""

    pattern: str
    port: int | None = None
    effect: str = "deny"
    description: str = ""


@dataclass(frozen=True)
class PolicyEvaluation:
    """Result of evaluating a host against the policy."""

    host: str
    port: int | None
    allowed: bool
    matched_rule: str | None
    reason: str


class NetworkPolicy:
    """Allowlist/denylist for outbound connections with logging."""

    def __init__(self, default_action: str = "allow") -> None:
        if default_action not in ("allow", "deny"):
            raise ValueError(f"default_action must be 'allow' or 'deny', got '{default_action}'")
        self._default_action = default_action
        self._rules: list[PolicyRule] = []
        self._log: deque[PolicyEvaluation] = deque(maxlen=10000)

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def add_rule(self, rule: PolicyRule) -> PolicyRule:
        """Add a rule. First-match wins, so order matters."""
        self._rules.append(rule)
        return rule

    def remove_rule(self, pattern: str) -> bool:
        """Remove first rule matching *pattern*. Returns True if found."""
        for i, r in enumerate(self._rules):
            if r.pattern == pattern:
                self._rules.pop(i)
                return True
        return False

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, host: str, port: int | None = None) -> PolicyEvaluation:
        """Evaluate *host* (and optional *port*) against rules. First match wins."""
        for rule in self._rules:
            if self._matches(rule, host, port):
                allowed = rule.effect == "allow"
                ev = PolicyEvaluation(
                    host=host,
                    port=port,
                    allowed=allowed,
                    matched_rule=rule.pattern,
                    reason=rule.description or f"matched rule '{rule.pattern}' ({rule.effect})",
                )
                self._log.append(ev)
                return ev

        # Default action
        allowed = self._default_action == "allow"
        ev = PolicyEvaluation(
            host=host,
            port=port,
            allowed=allowed,
            matched_rule=None,
            reason=f"default action: {self._default_action}",
        )
        self._log.append(ev)
        return ev

    def _matches(self, rule: PolicyRule, host: str, port: int | None) -> bool:
        """Check if *rule* matches the given *host* and *port*."""
        # Port check first (if rule specifies one)
        if rule.port is not None and port is not None and rule.port != port:
            return False

        pattern = rule.pattern
        if "*" in pattern:
            regex = re.escape(pattern).replace(r"\*", ".*")
            return bool(re.fullmatch(regex, host))
        return pattern in host

    # ------------------------------------------------------------------
    # Log / listing
    # ------------------------------------------------------------------

    def rules(self) -> list[PolicyRule]:
        """Return all configured rules."""
        return list(self._rules)

    def log(self) -> list[PolicyEvaluation]:
        """Return evaluation log."""
        return list(self._log)

    def clear_log(self) -> int:
        """Clear evaluation log and return count of removed entries."""
        count = len(self._log)
        self._log.clear()
        return count

    def summary(self) -> dict:
        """Return summary statistics."""
        allowed = sum(1 for e in self._log if e.allowed)
        return {
            "rules": len(self._rules),
            "evaluations": len(self._log),
            "allowed": allowed,
            "denied": len(self._log) - allowed,
            "default_action": self._default_action,
        }
