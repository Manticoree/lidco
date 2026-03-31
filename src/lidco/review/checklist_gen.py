"""Generate review checklists from diffs."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChecklistItem:
    """A single review checklist item."""

    category: str
    description: str
    priority: str = "medium"  # "high" / "medium" / "low"
    checked: bool = False


@dataclass
class ReviewChecklist:
    """Result of checklist generation."""

    items: list[ChecklistItem] = field(default_factory=list)
    summary: str = ""

    @property
    def high_priority_count(self) -> int:
        return sum(1 for i in self.items if i.priority == "high")

    def format(self) -> str:
        lines = [self.summary, ""]
        for item in self.items:
            mark = "[x]" if item.checked else "[ ]"
            lines.append(f"{mark} [{item.priority.upper()}] {item.category}: {item.description}")
        return "\n".join(lines)


# Default built-in rules ---------------------------------------------------

_DEFAULT_RULES: list[dict[str, Any]] = [
    {
        "name": "api_auth",
        "pattern": r"@(app|router)\.(get|post|put|patch|delete)\b",
        "category": "API",
        "description": "New API endpoint — verify authentication and authorization",
        "priority": "high",
    },
    {
        "name": "api_rate_limit",
        "pattern": r"@(app|router)\.(get|post|put|patch|delete)\b",
        "category": "API",
        "description": "New API endpoint — verify rate limiting is configured",
        "priority": "medium",
    },
    {
        "name": "api_validation",
        "pattern": r"@(app|router)\.(get|post|put|patch|delete)\b",
        "category": "API",
        "description": "New API endpoint — verify input validation",
        "priority": "high",
    },
    {
        "name": "new_file_tests",
        "pattern": r"^\+\+\+ b/.*\.py$",
        "category": "Testing",
        "description": "New file added — ensure corresponding tests exist",
        "priority": "medium",
    },
    {
        "name": "db_migration",
        "pattern": r"(CREATE TABLE|ALTER TABLE|DROP TABLE|ADD COLUMN|migrate|migration)",
        "category": "Database",
        "description": "Database change detected — verify migration script exists",
        "priority": "high",
    },
    {
        "name": "config_env",
        "pattern": r"(\.env|os\.environ|getenv|config\[|settings\[|\.yaml|\.toml)",
        "category": "Configuration",
        "description": "Config change — verify environment variables are documented",
        "priority": "medium",
    },
    {
        "name": "error_handling",
        "pattern": r"except\s*:",
        "category": "Error Handling",
        "description": "Bare except clause — use specific exception types",
        "priority": "high",
    },
    {
        "name": "error_handling_pass",
        "pattern": r"except\s+\w+.*:\s*\n\s+pass",
        "category": "Error Handling",
        "description": "Exception silently swallowed with pass — consider logging",
        "priority": "medium",
    },
]


class ReviewChecklistGenerator:
    """Generate review checklists from diff text."""

    def __init__(self) -> None:
        self._custom_rules: list[dict[str, Any]] = []

    def generate(
        self,
        diff_text: str,
        rules: list[dict[str, Any]] | None = None,
    ) -> ReviewChecklist:
        """Generate a checklist from *diff_text*.

        Parameters
        ----------
        diff_text:
            Unified diff text.
        rules:
            Optional list of custom rule dicts.  Each dict should have
            ``pattern``, ``category``, ``description``, and optionally
            ``priority`` (default ``"medium"``).  If *None*, built-in
            defaults are used.
        """
        active_rules = rules if rules is not None else _DEFAULT_RULES
        seen: set[str] = set()
        items: list[ChecklistItem] = []

        for rule in active_rules:
            pattern = rule.get("pattern", "")
            if not pattern:
                continue
            try:
                compiled = re.compile(pattern, re.MULTILINE)
            except re.error:
                continue
            if compiled.search(diff_text):
                key = (rule.get("category", ""), rule.get("description", ""))
                if key not in seen:
                    seen.add(key)
                    items.append(
                        ChecklistItem(
                            category=rule.get("category", "General"),
                            description=rule.get("description", ""),
                            priority=rule.get("priority", "medium"),
                        )
                    )

        summary = self._build_summary(items)
        return ReviewChecklist(items=items, summary=summary)

    # ------------------------------------------------------------------
    @staticmethod
    def _build_summary(items: list[ChecklistItem]) -> str:
        if not items:
            return "No review items generated."
        high = sum(1 for i in items if i.priority == "high")
        med = sum(1 for i in items if i.priority == "medium")
        low = sum(1 for i in items if i.priority == "low")
        parts = []
        if high:
            parts.append(f"{high} high")
        if med:
            parts.append(f"{med} medium")
        if low:
            parts.append(f"{low} low")
        return f"Review checklist: {len(items)} items ({', '.join(parts)} priority)."
