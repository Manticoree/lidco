"""Q246: System prompt builder — compose sections by priority with variable injection."""
from __future__ import annotations

import re
from dataclasses import dataclass

_VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")

# Rough token estimate: ~4 chars per token
_CHARS_PER_TOKEN = 4


@dataclass(frozen=True)
class _Section:
    """Internal immutable section."""

    name: str
    content: str
    priority: int


class SystemPromptBuilder:
    """Build a system prompt from prioritised sections with variable injection."""

    def __init__(self) -> None:
        self._sections: list[_Section] = []
        self._variables: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Section management
    # ------------------------------------------------------------------

    def add_section(
        self,
        name: str,
        content: str,
        priority: int = 0,
        condition: bool = True,
    ) -> None:
        """Add a named section. Higher priority appears first. Skipped if *condition* is False."""
        if not condition:
            return
        # Remove existing section with same name (immutable replace)
        self._sections = [
            s for s in self._sections if s.name != name
        ] + [_Section(name=name, content=content, priority=priority)]

    def remove_section(self, name: str) -> bool:
        """Remove a section by name. Returns True if found."""
        before = len(self._sections)
        self._sections = [s for s in self._sections if s.name != name]
        return len(self._sections) < before

    # ------------------------------------------------------------------
    # Variables
    # ------------------------------------------------------------------

    def set_variable(self, key: str, value: str) -> None:
        """Set a template variable for ``{{key}}`` replacement."""
        self._variables = {**self._variables, key: value}

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self, token_budget: int | None = None) -> str:
        """Compose sections ordered by priority (desc), inject variables, trim to budget."""
        ordered = sorted(self._sections, key=lambda s: s.priority, reverse=True)
        parts: list[str] = []
        for sec in ordered:
            text = _VAR_RE.sub(lambda m: self._variables.get(m.group(1), m.group(0)), sec.content)
            parts.append(text)
        result = "\n\n".join(parts)
        if token_budget is not None:
            max_chars = token_budget * _CHARS_PER_TOKEN
            if len(result) > max_chars:
                result = result[:max_chars]
        return result

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def sections(self) -> list[dict]:
        """Return section metadata as list of dicts."""
        return [
            {"name": s.name, "priority": s.priority, "length": len(s.content)}
            for s in sorted(self._sections, key=lambda s: s.priority, reverse=True)
        ]

    def token_estimate(self) -> int:
        """Rough token estimate for the full built prompt."""
        total_chars = sum(len(s.content) for s in self._sections)
        # Add separators
        if self._sections:
            total_chars += (len(self._sections) - 1) * 2  # "\n\n"
        return max(1, total_chars // _CHARS_PER_TOKEN)
