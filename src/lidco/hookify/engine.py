"""Hookify rule evaluation engine (Task 1048)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from lidco.hookify.rule import ActionType, EventType, HookifyRule, RuleMatch


class HookifyEngine:
    """Immutable rule engine — mutators return new instances."""

    def __init__(self, rules: tuple[HookifyRule, ...] = ()) -> None:
        self._rules = rules

    @property
    def rules(self) -> tuple[HookifyRule, ...]:
        """Return all registered rules."""
        return self._rules

    def add_rule(self, rule: HookifyRule) -> "HookifyEngine":
        """Return a new engine with *rule* appended."""
        return HookifyEngine(self._rules + (rule,))

    def remove_rule(self, name: str) -> "HookifyEngine":
        """Return a new engine without the rule named *name*."""
        return HookifyEngine(tuple(r for r in self._rules if r.name != name))

    def evaluate(self, event_type: EventType, content: str) -> tuple[RuleMatch, ...]:
        """Evaluate all enabled rules against *content*, returning matches."""
        matches: list[RuleMatch] = []
        for rule in sorted(self._rules, key=lambda r: -r.priority):
            if not rule.enabled:
                continue
            if rule.event_type not in (event_type, EventType.ALL):
                continue
            try:
                m = re.search(rule.pattern, content)
            except re.error:
                continue
            if m:
                matches.append(
                    RuleMatch(rule=rule, matched_text=m.group(0), event_type=event_type)
                )
        return tuple(matches)

    def is_blocked(self, event_type: EventType, content: str) -> bool:
        """Return ``True`` if any matching rule has action BLOCK."""
        matches = self.evaluate(event_type, content)
        return any(m.rule.action == ActionType.BLOCK for m in matches)

    def get_warnings(self, event_type: EventType, content: str) -> tuple[str, ...]:
        """Return warning messages from matching WARN rules."""
        matches = self.evaluate(event_type, content)
        return tuple(m.rule.message for m in matches if m.rule.action == ActionType.WARN)


__all__ = ["HookifyEngine"]
