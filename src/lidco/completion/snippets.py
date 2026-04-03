"""Snippet expansion system."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Snippet:
    """A reusable code snippet."""

    name: str
    trigger: str
    body: str
    description: str = ""
    tags: tuple[str, ...] = ()

    # Allow construction with list for tags (convert to tuple)
    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)


def _make_snippet(
    name: str,
    trigger: str,
    body: str,
    description: str = "",
    tags: list[str] | tuple[str, ...] | None = None,
) -> Snippet:
    """Helper to create a Snippet, accepting list or tuple for tags."""
    t = tuple(tags) if tags else ()
    return Snippet(name=name, trigger=trigger, body=body, description=description, tags=t)


class SnippetExpander:
    """Manage and expand code snippets with variable substitution."""

    def __init__(self) -> None:
        self._snippets: dict[str, Snippet] = {}

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, snippet: Snippet) -> None:
        """Register a snippet."""
        self._snippets = {**self._snippets, snippet.name: snippet}

    def remove(self, name: str) -> bool:
        """Remove a snippet by name.  Returns ``True`` if it existed."""
        if name not in self._snippets:
            return False
        self._snippets = {k: v for k, v in self._snippets.items() if k != name}
        return True

    # ------------------------------------------------------------------
    # Expansion
    # ------------------------------------------------------------------

    def expand(self, trigger: str, variables: dict[str, str] | None = None) -> str | None:
        """Expand the snippet whose trigger matches, replacing ``${var}`` placeholders."""
        snippet = self._find_by_trigger(trigger)
        if snippet is None:
            return None
        body = snippet.body
        if variables:
            for key, value in variables.items():
                body = body.replace(f"${{{key}}}", value)
        return body

    # ------------------------------------------------------------------
    # Search / list
    # ------------------------------------------------------------------

    def search(self, query: str) -> list[Snippet]:
        """Search snippets by name, trigger, description, or tags."""
        lower = query.lower()
        results: list[Snippet] = []
        for s in self._snippets.values():
            if (
                lower in s.name.lower()
                or lower in s.trigger.lower()
                or lower in s.description.lower()
                or any(lower in t.lower() for t in s.tags)
            ):
                results.append(s)
        return results

    def list_all(self) -> list[Snippet]:
        """Return all registered snippets."""
        return list(self._snippets.values())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _find_by_trigger(self, trigger: str) -> Snippet | None:
        for s in self._snippets.values():
            if s.trigger == trigger:
                return s
        return None
