"""
Conversation Template — multi-turn templates with {{variables}},
conditional branches, and YAML serialization.

Stdlib only — no external dependencies.
"""

from __future__ import annotations

import copy
import re
import time
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ConversationTemplateError(Exception):
    """Raised on template errors."""


class UndefinedVariableError(ConversationTemplateError):
    """Raised when a required variable is missing."""


# ---------------------------------------------------------------------------
# Data classes (frozen for immutability)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TemplateVariable:
    """A variable declaration in a template."""

    name: str
    description: str = ""
    default: Any = None
    required: bool = True


@dataclass(frozen=True)
class ConversationTurn:
    """A single turn in a conversation template."""

    role: str  # "user", "assistant", "system"
    content: str  # May contain {{variables}}
    condition: str | None = None  # Optional condition for this turn


@dataclass(frozen=True)
class ConversationBranch:
    """A conditional branch in the conversation."""

    condition: str
    turns: tuple[ConversationTurn, ...] = ()


@dataclass(frozen=True)
class ConversationTemplate:
    """A complete conversation template."""

    name: str
    description: str = ""
    variables: tuple[TemplateVariable, ...] = ()
    turns: tuple[ConversationTurn, ...] = ()
    branches: tuple[ConversationBranch, ...] = ()
    tags: tuple[str, ...] = ()
    version: str = "1.0"
    created_at: float = 0.0

    def variable_names(self) -> list[str]:
        """Return names of all declared variables."""
        return [v.name for v in self.variables]

    def required_variables(self) -> list[str]:
        """Return names of all required variables."""
        return [v.name for v in self.variables if v.required]


# ---------------------------------------------------------------------------
# Variable substitution
# ---------------------------------------------------------------------------

_VAR_RE = re.compile(r'\{\{\s*(\w+)\s*\}\}')
_COND_RE = re.compile(r'^\s*(\w+)\s*(==|!=|>|<|>=|<=)\s*(.+)\s*$')


def _eval_condition(condition: str, variables: dict[str, Any]) -> bool:
    """Evaluate a simple condition string against variables."""
    condition = condition.strip()
    if not condition:
        return True

    # Handle 'not x'
    if condition.startswith("not "):
        return not _eval_condition(condition[4:], variables)

    # Handle 'a and b'
    if " and " in condition:
        parts = condition.split(" and ", 1)
        return _eval_condition(parts[0], variables) and _eval_condition(parts[1], variables)

    # Handle 'a or b'
    if " or " in condition:
        parts = condition.split(" or ", 1)
        return _eval_condition(parts[0], variables) or _eval_condition(parts[1], variables)

    # Handle comparisons
    m = _COND_RE.match(condition)
    if m:
        var_name, op, raw_val = m.group(1), m.group(2), m.group(3).strip()
        left = variables.get(var_name)
        # Parse right-hand value
        right: Any = raw_val
        if raw_val.startswith('"') and raw_val.endswith('"'):
            right = raw_val[1:-1]
        elif raw_val.startswith("'") and raw_val.endswith("'"):
            right = raw_val[1:-1]
        elif raw_val == "True":
            right = True
        elif raw_val == "False":
            right = False
        elif raw_val == "None":
            right = None
        else:
            try:
                right = int(raw_val)
            except ValueError:
                try:
                    right = float(raw_val)
                except ValueError:
                    right = variables.get(raw_val, raw_val)

        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == ">":
            return left > right
        if op == "<":
            return left < right
        if op == ">=":
            return left >= right
        if op == "<=":
            return left <= right

    # Truthy check on variable
    return bool(variables.get(condition))


def substitute(text: str, variables: dict[str, Any]) -> str:
    """Substitute {{var}} placeholders in text."""
    def _replace(m: re.Match) -> str:
        name = m.group(1)
        val = variables.get(name)
        if val is None:
            return m.group(0)  # leave as-is if not found
        return str(val)
    return _VAR_RE.sub(_replace, text)


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

@dataclass
class RenderedTurn:
    """A rendered conversation turn."""

    role: str
    content: str


class ConversationRenderer:
    """Render a ConversationTemplate with given variables."""

    def __init__(self, strict: bool = False) -> None:
        self._strict = strict

    def render(
        self,
        template: ConversationTemplate,
        variables: dict[str, Any] | None = None,
    ) -> list[RenderedTurn]:
        """Render template into a list of turns."""
        variables = dict(variables or {})

        # Apply defaults for missing variables
        for v in template.variables:
            if v.name not in variables:
                if v.required and v.default is None and self._strict:
                    raise UndefinedVariableError(
                        f"Required variable '{v.name}' not provided"
                    )
                if v.default is not None:
                    variables[v.name] = v.default

        result: list[RenderedTurn] = []

        # Render main turns
        for turn in template.turns:
            if turn.condition and not _eval_condition(turn.condition, variables):
                continue
            content = substitute(turn.content, variables)
            result.append(RenderedTurn(role=turn.role, content=content))

        # Render branches
        for branch in template.branches:
            if _eval_condition(branch.condition, variables):
                for turn in branch.turns:
                    if turn.condition and not _eval_condition(turn.condition, variables):
                        continue
                    content = substitute(turn.content, variables)
                    result.append(RenderedTurn(role=turn.role, content=content))

        return result

    def render_text(
        self,
        template: ConversationTemplate,
        variables: dict[str, Any] | None = None,
    ) -> str:
        """Render template as formatted text."""
        turns = self.render(template, variables)
        lines: list[str] = []
        for t in turns:
            lines.append(f"[{t.role}] {t.content}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# YAML serialization (stdlib-only, simple format)
# ---------------------------------------------------------------------------

def template_to_dict(template: ConversationTemplate) -> dict[str, Any]:
    """Serialize a ConversationTemplate to a plain dict."""
    return {
        "name": template.name,
        "description": template.description,
        "version": template.version,
        "tags": list(template.tags),
        "created_at": template.created_at,
        "variables": [
            {
                "name": v.name,
                "description": v.description,
                "default": v.default,
                "required": v.required,
            }
            for v in template.variables
        ],
        "turns": [
            {
                "role": t.role,
                "content": t.content,
                "condition": t.condition,
            }
            for t in template.turns
        ],
        "branches": [
            {
                "condition": b.condition,
                "turns": [
                    {"role": t.role, "content": t.content, "condition": t.condition}
                    for t in b.turns
                ],
            }
            for b in template.branches
        ],
    }


def template_from_dict(data: dict[str, Any]) -> ConversationTemplate:
    """Deserialize a ConversationTemplate from a plain dict."""
    variables = tuple(
        TemplateVariable(
            name=v["name"],
            description=v.get("description", ""),
            default=v.get("default"),
            required=v.get("required", True),
        )
        for v in data.get("variables", [])
    )
    turns = tuple(
        ConversationTurn(
            role=t["role"],
            content=t["content"],
            condition=t.get("condition"),
        )
        for t in data.get("turns", [])
    )
    branches = tuple(
        ConversationBranch(
            condition=b["condition"],
            turns=tuple(
                ConversationTurn(
                    role=t["role"],
                    content=t["content"],
                    condition=t.get("condition"),
                )
                for t in b.get("turns", [])
            ),
        )
        for b in data.get("branches", [])
    )
    return ConversationTemplate(
        name=data["name"],
        description=data.get("description", ""),
        variables=variables,
        turns=turns,
        branches=branches,
        tags=tuple(data.get("tags", [])),
        version=data.get("version", "1.0"),
        created_at=data.get("created_at", 0.0),
    )


def template_to_yaml(template: ConversationTemplate) -> str:
    """Serialize template to a simple YAML-like string format."""
    lines: list[str] = []
    lines.append(f"name: {template.name}")
    lines.append(f"description: {template.description}")
    lines.append(f"version: {template.version}")
    if template.tags:
        lines.append(f"tags: [{', '.join(template.tags)}]")
    if template.variables:
        lines.append("variables:")
        for v in template.variables:
            lines.append(f"  - name: {v.name}")
            if v.description:
                lines.append(f"    description: {v.description}")
            if v.default is not None:
                lines.append(f"    default: {v.default}")
            lines.append(f"    required: {v.required}")
    if template.turns:
        lines.append("turns:")
        for t in template.turns:
            lines.append(f"  - role: {t.role}")
            lines.append(f"    content: {t.content}")
            if t.condition:
                lines.append(f"    condition: {t.condition}")
    if template.branches:
        lines.append("branches:")
        for b in template.branches:
            lines.append(f"  - condition: {b.condition}")
            lines.append("    turns:")
            for t in b.turns:
                lines.append(f"      - role: {t.role}")
                lines.append(f"        content: {t.content}")
                if t.condition:
                    lines.append(f"        condition: {t.condition}")
    return "\n".join(lines)
