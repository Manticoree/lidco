"""TagManager — in-memory git tag management (stdlib only, no subprocess)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Tag:
    """Represents a git-style tag."""

    name: str
    message: str = ""
    annotated: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TagManager:
    """Manage an in-memory collection of tags."""

    def __init__(self) -> None:
        self._tags: list[Tag] = []

    @property
    def tags(self) -> list[Tag]:
        return list(self._tags)

    # ------------------------------------------------------------------ #
    # CRUD                                                                 #
    # ------------------------------------------------------------------ #

    def create_tag(self, name: str, message: str = "") -> Tag:
        """Create a lightweight tag.

        Raises ``ValueError`` if a tag with the same name already exists.
        """
        if any(t.name == name for t in self._tags):
            raise ValueError(f"Tag '{name}' already exists")
        tag = Tag(name=name, message=message, annotated=False)
        self._tags = [*self._tags, tag]
        return tag

    def annotated(self, name: str, message: str) -> Tag:
        """Create an annotated tag (message is required).

        Raises ``ValueError`` if *message* is empty or tag already exists.
        """
        if not message:
            raise ValueError("Annotated tags require a non-empty message")
        if any(t.name == name for t in self._tags):
            raise ValueError(f"Tag '{name}' already exists")
        tag = Tag(name=name, message=message, annotated=True)
        self._tags = [*self._tags, tag]
        return tag

    def list_tags(self) -> list[Tag]:
        """Return all tags sorted by creation time (newest first)."""
        return sorted(self._tags, key=lambda t: t.created_at, reverse=True)

    def delete_tag(self, name: str) -> bool:
        """Delete a tag by name. Returns ``True`` if it existed."""
        before = len(self._tags)
        self._tags = [t for t in self._tags if t.name != name]
        return len(self._tags) < before

    def latest(self) -> Optional[Tag]:
        """Return the most recently created tag, or ``None`` if empty."""
        if not self._tags:
            return None
        return max(self._tags, key=lambda t: t.created_at)

    def tags_for_version(self, pattern: str) -> list[Tag]:
        """Return tags whose name matches *pattern* (glob-style with ``*``).

        ``*`` is converted to ``.*`` for regex matching.
        """
        regex = re.compile("^" + re.escape(pattern).replace(r"\*", ".*") + "$")
        return [t for t in self._tags if regex.match(t.name)]
