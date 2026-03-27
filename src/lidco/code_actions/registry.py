"""Code Actions Registry — quick-fix suggestions keyed by error patterns (stdlib only).

Inspired by VS Code's "Quick Fix" / Cursor's code actions: register actions
that match error messages or code patterns and return actionable suggestions
with optional fix templates.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable


class CodeActionError(Exception):
    """Raised when a code action cannot be applied."""


@dataclass
class CodeAction:
    """A single quick-fix action definition."""

    id: str
    title: str
    description: str = ""
    pattern: str = ""          # regex matched against error/code text
    fix_template: str = ""     # template string; use {match} for captured group
    severity: str = "warning"  # "error" | "warning" | "info" | "hint"
    tags: list[str] = field(default_factory=list)

    def matches(self, text: str) -> re.Match[str] | None:
        """Return regex match if this action applies to *text*, else None."""
        if not self.pattern:
            return None
        try:
            return re.search(self.pattern, text)
        except re.error:
            return None

    def apply_fix(self, match: re.Match[str] | None = None) -> str:
        """Render fix_template, substituting {match} with the matched text."""
        if not self.fix_template:
            return self.description or self.title
        matched_text = match.group(0) if match else ""
        return self.fix_template.replace("{match}", matched_text)


@dataclass
class ActionMatch:
    """A code action that matched a specific piece of text."""

    action: CodeAction
    matched_text: str
    fix: str
    context: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.action.id

    @property
    def title(self) -> str:
        return self.action.title


class CodeActionsRegistry:
    """Registry of code actions looked up by error message or code pattern.

    Usage::

        reg = CodeActionsRegistry()

        reg.register(CodeAction(
            id="undefined-var",
            title="Import missing symbol",
            pattern=r"NameError: name '(\\w+)' is not defined",
            fix_template="Add 'import {match}' or define it above this line.",
            severity="error",
        ))

        matches = reg.find_actions("NameError: name 'requests' is not defined")
        for m in matches:
            print(m.title, "→", m.fix)
    """

    def __init__(self) -> None:
        self._actions: dict[str, CodeAction] = {}

    # ------------------------------------------------------------------ #
    # Registration                                                         #
    # ------------------------------------------------------------------ #

    def register(self, action: CodeAction) -> None:
        if not action.id:
            raise CodeActionError("CodeAction.id must not be empty")
        self._actions[action.id] = action

    def unregister(self, action_id: str) -> bool:
        """Remove an action by id. Returns True if it existed."""
        return self._actions.pop(action_id, None) is not None

    def get(self, action_id: str) -> CodeAction | None:
        return self._actions.get(action_id)

    def list_actions(self, severity: str | None = None) -> list[CodeAction]:
        actions = list(self._actions.values())
        if severity:
            actions = [a for a in actions if a.severity == severity]
        return sorted(actions, key=lambda a: a.id)

    def __len__(self) -> int:
        return len(self._actions)

    # ------------------------------------------------------------------ #
    # Lookup                                                               #
    # ------------------------------------------------------------------ #

    def find_actions(
        self,
        text: str,
        *,
        severity: str | None = None,
        tags: list[str] | None = None,
    ) -> list[ActionMatch]:
        """Return all actions whose pattern matches *text*."""
        results: list[ActionMatch] = []
        candidates = self.list_actions(severity=severity)

        if tags:
            tag_set = set(tags)
            candidates = [a for a in candidates if tag_set & set(a.tags)]

        for action in candidates:
            m = action.matches(text)
            if m is not None:
                fix = action.apply_fix(m)
                results.append(
                    ActionMatch(
                        action=action,
                        matched_text=m.group(0),
                        fix=fix,
                    )
                )
        return results

    def find_by_tag(self, tag: str) -> list[CodeAction]:
        return [a for a in self._actions.values() if tag in a.tags]

    # ------------------------------------------------------------------ #
    # Built-in common actions                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    def with_defaults(cls) -> "CodeActionsRegistry":
        """Return a registry pre-loaded with common Python quick-fixes."""
        reg = cls()
        defaults = [
            CodeAction(
                id="undefined-name",
                title="Add missing import",
                pattern=r"NameError: name '(\w+)' is not defined",
                fix_template="Add 'import {match}' or define '{match}' before use.",
                severity="error",
                tags=["python", "import"],
            ),
            CodeAction(
                id="unused-import",
                title="Remove unused import",
                pattern=r"imported but unused",
                fix_template="Remove the unused import statement.",
                severity="warning",
                tags=["python", "import"],
            ),
            CodeAction(
                id="type-error-none",
                title="Check for None before use",
                pattern=r"TypeError: 'NoneType' object",
                fix_template="Add a None check: 'if value is not None: ...'",
                severity="error",
                tags=["python", "types"],
            ),
            CodeAction(
                id="indentation-error",
                title="Fix indentation",
                pattern=r"IndentationError",
                fix_template="Check that indentation uses consistent spaces (4 spaces per level).",
                severity="error",
                tags=["python", "style"],
            ),
            CodeAction(
                id="missing-return",
                title="Add return statement",
                pattern=r"expected return value|missing return",
                fix_template="Ensure all code paths return a value.",
                severity="warning",
                tags=["python", "types"],
            ),
            CodeAction(
                id="console-log",
                title="Remove console.log",
                pattern=r"console\.log\(",
                fix_template="Remove or replace console.log() with proper logging.",
                severity="warning",
                tags=["javascript", "style"],
            ),
            CodeAction(
                id="hardcoded-secret",
                title="Move secret to env var",
                pattern=r"(password|api_key|secret|token)\s*=\s*['\"][^'\"]{6,}['\"]",
                fix_template="Move this secret to an environment variable.",
                severity="error",
                tags=["security"],
            ),
        ]
        for action in defaults:
            reg.register(action)
        return reg

    # ------------------------------------------------------------------ #
    # Bulk analysis                                                        #
    # ------------------------------------------------------------------ #

    def analyze(self, text: str) -> dict[str, list[ActionMatch]]:
        """Group all matches by severity."""
        matches = self.find_actions(text)
        grouped: dict[str, list[ActionMatch]] = {}
        for m in matches:
            grouped.setdefault(m.action.severity, []).append(m)
        return grouped
