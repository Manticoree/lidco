"""Content filter — allow / deny / redact rules applied before LLM calls."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FilterRule:
    """A single content filter rule."""

    name: str
    pattern: str
    action: str  # allow / deny / redact
    priority: int = 0


@dataclass(frozen=True)
class FilterResult:
    """Outcome of filtering content."""

    original_length: int
    filtered_length: int
    rules_applied: list[str]
    blocked: bool


class ContentFilter:
    """Apply ordered rules to content before it leaves the system."""

    def __init__(self, default_action: str = "allow") -> None:
        self._default_action = default_action
        self._rules: dict[str, FilterRule] = {}

    # ------------------------------------------------------------------

    def add_rule(self, rule: FilterRule) -> FilterRule:
        self._rules[rule.name] = rule
        return rule

    def remove_rule(self, name: str) -> bool:
        return self._rules.pop(name, None) is not None

    def filter(self, content: str) -> tuple[str, FilterResult]:
        """Return (filtered_content, result)."""
        original_length = len(content)
        applied: list[str] = []
        blocked = False
        sorted_rules = sorted(self._rules.values(), key=lambda r: -r.priority)
        for rule in sorted_rules:
            if re.search(rule.pattern, content):
                applied.append(rule.name)
                if rule.action == "deny":
                    blocked = True
                    break
                if rule.action == "redact":
                    content = re.sub(rule.pattern, "[REDACTED]", content)
        return content, FilterResult(
            original_length=original_length,
            filtered_length=len(content),
            rules_applied=applied,
            blocked=blocked,
        )

    def check(self, content: str) -> FilterResult:
        """Check content without modifying it."""
        _, result = self.filter(content)
        return result

    def rules(self) -> list[FilterRule]:
        return sorted(self._rules.values(), key=lambda r: -r.priority)

    def summary(self) -> dict:
        return {
            "rule_count": len(self._rules),
            "default_action": self._default_action,
            "rules": [r.name for r in self.rules()],
        }
