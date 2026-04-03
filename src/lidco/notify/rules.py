"""Rule-based notification evaluation with cooldown support."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class NotifyRule:
    """A notification rule definition."""

    name: str
    event: str
    level: str = "info"
    cooldown_seconds: float = 0.0
    enabled: bool = True


@dataclass(frozen=True)
class RuleMatch:
    """Result of evaluating an event against rules."""

    rule_name: str
    event: str
    should_notify: bool
    reason: str


class NotificationRules:
    """Manage and evaluate notification rules with cooldown."""

    def __init__(self) -> None:
        self._rules: dict[str, NotifyRule] = {}
        self._last_fired: dict[str, float] = {}
        # Default rules
        self.add_rule(NotifyRule(name="default_completion", event="completion", level="success"))
        self.add_rule(NotifyRule(name="default_error", event="error", level="error"))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_rule(self, rule: NotifyRule) -> NotifyRule:
        self._rules[rule.name] = rule
        return rule

    def remove_rule(self, name: str) -> bool:
        return self._rules.pop(name, None) is not None

    def enable(self, name: str) -> bool:
        rule = self._rules.get(name)
        if rule is None:
            return False
        rule.enabled = True
        return True

    def disable(self, name: str) -> bool:
        rule = self._rules.get(name)
        if rule is None:
            return False
        rule.enabled = False
        return True

    def evaluate(self, event: str) -> RuleMatch:
        """Evaluate rules for *event*. Returns match for first matching rule."""
        for rule in self._rules.values():
            if rule.event != event:
                continue
            if not rule.enabled:
                return RuleMatch(
                    rule_name=rule.name,
                    event=event,
                    should_notify=False,
                    reason="rule disabled",
                )
            # Cooldown check
            if rule.cooldown_seconds > 0:
                last = self._last_fired.get(rule.name, 0.0)
                elapsed = time.time() - last
                if elapsed < rule.cooldown_seconds:
                    return RuleMatch(
                        rule_name=rule.name,
                        event=event,
                        should_notify=False,
                        reason=f"cooldown ({rule.cooldown_seconds}s)",
                    )
            self._last_fired[rule.name] = time.time()
            return RuleMatch(
                rule_name=rule.name,
                event=event,
                should_notify=True,
                reason="matched",
            )
        return RuleMatch(
            rule_name="",
            event=event,
            should_notify=False,
            reason="no matching rule",
        )

    def rules(self) -> list[NotifyRule]:
        return list(self._rules.values())

    def summary(self) -> dict:
        return {
            "total": len(self._rules),
            "enabled": sum(1 for r in self._rules.values() if r.enabled),
            "disabled": sum(1 for r in self._rules.values() if not r.enabled),
        }
