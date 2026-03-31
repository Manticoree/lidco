"""AI-powered permission classifier for tool calls — Q160."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ClassificationResult:
    """Result of a permission classification."""

    action: str  # "allow", "deny", or "ask"
    confidence: float  # 0.0–1.0
    reason: str


# ---------------------------------------------------------------------------
# Built-in pattern tables
# ---------------------------------------------------------------------------

_DESTRUCTIVE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\brm\s+(-\w*\s+)*-rf?\b", re.IGNORECASE),
    re.compile(r"\brm\s+-rf\b", re.IGNORECASE),
    re.compile(r"\brmdir\b", re.IGNORECASE),
    re.compile(r"\bdrop\s+table\b", re.IGNORECASE),
    re.compile(r"\bdrop\s+database\b", re.IGNORECASE),
    re.compile(r"\btruncate\s+table\b", re.IGNORECASE),
    re.compile(r"\bdelete\s+from\b", re.IGNORECASE),
    re.compile(r"\bformat\s+[a-z]:", re.IGNORECASE),
    re.compile(r"\bmkfs\b", re.IGNORECASE),
    re.compile(r"\bdd\s+if=", re.IGNORECASE),
    re.compile(r"\bgit\s+push\s+--force\b", re.IGNORECASE),
    re.compile(r"\bgit\s+reset\s+--hard\b", re.IGNORECASE),
    re.compile(r"\bgit\s+clean\s+-fd\b", re.IGNORECASE),
    re.compile(r"\bchmod\s+777\b", re.IGNORECASE),
    re.compile(r"\b:(){ :\|:& };:", re.IGNORECASE),  # fork bomb
    re.compile(r"\bcurl\b.*\|\s*bash\b", re.IGNORECASE),
    re.compile(r"\bwget\b.*\|\s*bash\b", re.IGNORECASE),
]

_SAFE_TOOL_NAMES: frozenset[str] = frozenset({
    "read", "grep", "glob", "cat", "head", "tail", "ls", "find",
    "file_read", "file_search", "content_search", "directory_list",
    "Read", "Grep", "Glob",
})


class PermissionClassifier:
    """Classify tool calls as allow / deny / ask based on rules."""

    def __init__(self, rules: list[str] | None = None) -> None:
        self._rules: list[str] = list(rules) if rules else []
        self._stats: dict[str, int] = {"allow": 0, "deny": 0, "ask": 0}

    # -- rule management ----------------------------------------------------

    def add_rule(self, rule: str) -> None:
        """Append a prose rule."""
        if rule and rule not in self._rules:
            self._rules.append(rule)

    def remove_rule(self, rule: str) -> None:
        """Remove a prose rule (no-op if missing)."""
        try:
            self._rules.remove(rule)
        except ValueError:
            pass

    def list_rules(self) -> list[str]:
        """Return a copy of the current rule list."""
        return list(self._rules)

    # -- classification -----------------------------------------------------

    def classify(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        context: str = "",
    ) -> ClassificationResult:
        """Classify a tool invocation.

        Evaluation order:
        1. Built-in deny (destructive patterns) — highest priority.
        2. Built-in allow (safe read-only tools).
        3. Custom rules (keyword matching).
        4. Default: ask.
        """
        combined = _combine_text(tool_name, tool_args, context)

        # 1. Destructive pattern check
        for pat in _DESTRUCTIVE_PATTERNS:
            if pat.search(combined):
                result = ClassificationResult(
                    action="deny",
                    confidence=1.0,
                    reason=f"Matches destructive pattern: {pat.pattern}",
                )
                self._stats["deny"] += 1
                return result

        # 2. Safe tool shortcut
        if tool_name in _SAFE_TOOL_NAMES:
            result = ClassificationResult(
                action="allow",
                confidence=1.0,
                reason=f"Tool '{tool_name}' is on the built-in safe list.",
            )
            self._stats["allow"] += 1
            return result

        # 3. Custom rules
        for rule in self._rules:
            rule_result = _evaluate_rule(rule, tool_name, tool_args, combined)
            if rule_result is not None:
                self._stats[rule_result.action] += 1
                return rule_result

        # 4. Default
        result = ClassificationResult(
            action="ask",
            confidence=0.5,
            reason="No matching rule; asking user for permission.",
        )
        self._stats["ask"] += 1
        return result

    # -- stats --------------------------------------------------------------

    @property
    def stats(self) -> dict[str, int]:
        """Return classification counts."""
        return dict(self._stats)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _combine_text(tool_name: str, tool_args: dict[str, Any], context: str) -> str:
    """Build a single string from all inputs for pattern matching."""
    parts = [tool_name]
    for v in tool_args.values():
        parts.append(str(v))
    if context:
        parts.append(context)
    return " ".join(parts)


def _evaluate_rule(
    rule: str,
    tool_name: str,
    tool_args: dict[str, Any],
    combined: str,
) -> ClassificationResult | None:
    """Evaluate one prose rule via keyword matching.

    Supported formats (case-insensitive):
      - "allow <keyword>"   — allow if keyword present
      - "deny <keyword>"    — deny if keyword present
      - "ask <keyword>"     — ask if keyword present
    """
    lower = rule.strip().lower()
    for action in ("allow", "deny", "ask"):
        if lower.startswith(action + " "):
            keyword = lower[len(action) + 1:].strip()
            if not keyword:
                continue
            if keyword in combined.lower():
                confidence = 0.9 if action in ("allow", "deny") else 0.7
                return ClassificationResult(
                    action=action,
                    confidence=confidence,
                    reason=f"Custom rule matched: '{rule}'",
                )
    return None
