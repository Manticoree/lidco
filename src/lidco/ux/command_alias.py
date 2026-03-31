"""Q145 Task 858: Command alias system."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Alias:
    """A command alias mapping."""

    name: str
    expansion: str
    description: str = ""
    usage_count: int = 0


class CommandAlias:
    """Manages command aliases for shorthand expansions."""

    def __init__(self) -> None:
        self._aliases: dict[str, Alias] = {}

    def add(self, name: str, expansion: str, description: str = "") -> None:
        """Register or update an alias."""
        self._aliases[name] = Alias(
            name=name, expansion=expansion, description=description
        )

    def remove(self, name: str) -> bool:
        """Remove an alias. Returns True if it existed."""
        if name in self._aliases:
            del self._aliases[name]
            return True
        return False

    def resolve(self, input_str: str) -> str:
        """Expand alias if *input_str* starts with a known alias name.

        Returns the expanded string (alias replaced) or the original input.
        """
        parts = input_str.strip().split(maxsplit=1)
        if not parts:
            return input_str
        name = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        alias = self._aliases.get(name)
        if alias is None:
            return input_str
        alias.usage_count += 1
        if rest:
            return f"{alias.expansion} {rest}"
        return alias.expansion

    def list_aliases(self) -> list[Alias]:
        """Return all aliases sorted by name."""
        return sorted(self._aliases.values(), key=lambda a: a.name)

    def is_alias(self, name: str) -> bool:
        """Check whether *name* is a registered alias."""
        return name in self._aliases

    def most_used(self, n: int = 5) -> list[Alias]:
        """Return the *n* most used aliases by usage_count."""
        ranked = sorted(
            self._aliases.values(), key=lambda a: a.usage_count, reverse=True
        )
        return ranked[:n]
