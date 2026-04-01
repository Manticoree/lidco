"""YAML-frontmatter persistence for hookify rules (Task 1050)."""
from __future__ import annotations

import os
import re
from pathlib import Path

from lidco.hookify.rule import ActionType, EventType, HookifyRule


def _rule_to_frontmatter(rule: HookifyRule) -> str:
    """Serialize a rule to YAML frontmatter + message body."""
    lines = [
        "---",
        f"name: {rule.name}",
        f"enabled: {str(rule.enabled).lower()}",
        f"event_type: {rule.event_type.value}",
        f"pattern: {rule.pattern}",
        f"action: {rule.action.value}",
        f"created_at: {rule.created_at}",
        f"priority: {rule.priority}",
        "---",
        rule.message,
    ]
    return "\n".join(lines) + "\n"


def _parse_frontmatter(text: str) -> HookifyRule:
    """Parse a YAML-frontmatter .md file into a HookifyRule."""
    m = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not m:
        raise ValueError("Invalid frontmatter format")
    meta_block = m.group(1)
    message = m.group(2).strip()
    meta: dict[str, str] = {}
    for line in meta_block.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()
    return HookifyRule(
        name=meta.get("name", ""),
        enabled=meta.get("enabled", "true").lower() == "true",
        event_type=EventType(meta.get("event_type", "all")),
        pattern=meta.get("pattern", ""),
        action=ActionType(meta.get("action", "warn")),
        message=message,
        created_at=meta.get("created_at", ""),
        priority=int(meta.get("priority", "0")),
    )


class RulePersistence:
    """Save / load hookify rules as .md files with YAML frontmatter."""

    def save_rule(self, rule: HookifyRule, directory: str) -> str:
        """Save *rule* to *directory*, returning the file path."""
        path = os.path.join(directory, f"{rule.name}.md")
        os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(_rule_to_frontmatter(rule))
        return path

    def load_rule(self, path: str) -> HookifyRule:
        """Load a single rule from *path*."""
        with open(path, "r", encoding="utf-8") as f:
            return _parse_frontmatter(f.read())

    def load_all(self, directory: str) -> tuple[HookifyRule, ...]:
        """Load all .md rule files from *directory*."""
        if not os.path.isdir(directory):
            return ()
        rules: list[HookifyRule] = []
        for name in sorted(os.listdir(directory)):
            if name.endswith(".md"):
                rules.append(self.load_rule(os.path.join(directory, name)))
        return tuple(rules)

    def delete_rule(self, name: str, directory: str) -> bool:
        """Delete the rule file for *name*. Returns True if deleted."""
        path = os.path.join(directory, f"{name}.md")
        if os.path.isfile(path):
            os.remove(path)
            return True
        return False


__all__ = ["RulePersistence"]
