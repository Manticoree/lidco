"""AlertRuleEngine — conditional alert rules with evaluation (stdlib only)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

_VALID_ACTIONS = frozenset({"notify", "warn", "block"})


@dataclass
class Rule:
    """A single alert rule."""

    name: str
    condition_fn: Callable[[dict], bool]
    action: str
    message_template: str
    enabled: bool = True


class AlertRuleEngine:
    """Manages alert rules and evaluates them against context dicts."""

    def __init__(self) -> None:
        self._rules: dict[str, Rule] = {}
        self._trigger_counts: dict[str, int] = {}

    # ------------------------------------------------------------------ CRUD

    def add_rule(
        self,
        name: str,
        condition_fn: Callable[[dict], bool],
        action: str,
        message_template: str,
    ) -> Rule:
        """Add (or replace) a named rule."""
        if action not in _VALID_ACTIONS:
            raise ValueError(f"Invalid action {action!r}; must be one of {sorted(_VALID_ACTIONS)}")
        rule = Rule(
            name=name,
            condition_fn=condition_fn,
            action=action,
            message_template=message_template,
        )
        self._rules[name] = rule
        self._trigger_counts.setdefault(name, 0)
        return rule

    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name.  Returns True if found."""
        if name in self._rules:
            del self._rules[name]
            return True
        return False

    # ------------------------------------------------------------------ enable / disable

    def enable(self, name: str) -> None:
        """Enable a rule by name."""
        if name in self._rules:
            self._rules[name].enabled = True

    def disable(self, name: str) -> None:
        """Disable a rule by name."""
        if name in self._rules:
            self._rules[name].enabled = False

    # ------------------------------------------------------------------ evaluate

    def evaluate(self, context: dict) -> list[tuple[Rule, str]]:
        """Evaluate all enabled rules against *context*.

        Returns list of ``(rule, formatted_message)`` for triggered rules.
        """
        triggered: list[tuple[Rule, str]] = []
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            try:
                if rule.condition_fn(context):
                    msg = rule.message_template.format(**context)
                    triggered.append((rule, msg))
                    self._trigger_counts[rule.name] = self._trigger_counts.get(rule.name, 0) + 1
            except Exception:
                # Rule condition or template failed — skip silently
                continue
        return triggered

    # ------------------------------------------------------------------ list / stats

    def list_rules(self) -> list[Rule]:
        """Return all registered rules."""
        return list(self._rules.values())

    def triggered_count(self, name: str) -> int:
        """Return how many times a rule has fired."""
        return self._trigger_counts.get(name, 0)
