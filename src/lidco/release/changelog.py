"""ChangelogGenerator2 — build Keep-a-Changelog-style changelogs (stdlib only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class ChangelogEntry:
    """A single changelog entry."""

    type: str
    message: str
    pr_url: str = ""


class ChangelogGenerator2:
    """Accumulates changelog entries and renders them in various formats."""

    # Canonical ordering of change types
    TYPE_ORDER: list[str] = [
        "added",
        "changed",
        "deprecated",
        "removed",
        "fixed",
        "security",
    ]

    def __init__(self) -> None:
        self._entries: list[ChangelogEntry] = []

    # ------------------------------------------------------------------ #
    # Mutation                                                             #
    # ------------------------------------------------------------------ #

    def add_entry(self, type: str, message: str, pr_url: str = "") -> None:
        """Add a changelog entry.

        *type* should be one of added/changed/deprecated/removed/fixed/security.
        """
        self._entries = [*self._entries, ChangelogEntry(type=type.lower(), message=message, pr_url=pr_url)]

    @property
    def entries(self) -> list[ChangelogEntry]:
        return list(self._entries)

    # ------------------------------------------------------------------ #
    # Grouping                                                             #
    # ------------------------------------------------------------------ #

    def group_by_type(self) -> dict[str, list[ChangelogEntry]]:
        """Group entries by their type, returning a dict keyed by type."""
        groups: dict[str, list[ChangelogEntry]] = {}
        for entry in self._entries:
            groups.setdefault(entry.type, [])
            groups[entry.type] = [*groups[entry.type], entry]
        return groups

    # ------------------------------------------------------------------ #
    # Rendering                                                            #
    # ------------------------------------------------------------------ #

    def generate(self, version: str) -> str:
        """Render a simple markdown changelog for *version*."""
        if not self._entries:
            return f"# {version}\n\nNo changes."
        lines = [f"# {version}", ""]
        for entry in self._entries:
            pr_suffix = f" ({entry.pr_url})" if entry.pr_url else ""
            lines.append(f"- **{entry.type}**: {entry.message}{pr_suffix}")
        return "\n".join(lines)

    def keep_a_changelog_format(self, version: str, release_date: str | None = None) -> str:
        """Render in `Keep a Changelog <https://keepachangelog.com>`_ format.

        *release_date* defaults to today if not provided.
        """
        if release_date is None:
            release_date = date.today().isoformat()

        groups = self.group_by_type()
        lines = [f"## [{version}] - {release_date}", ""]

        # Render in canonical order, then any extras
        rendered: set[str] = set()
        for type_key in self.TYPE_ORDER:
            if type_key in groups:
                self._render_group(lines, type_key, groups[type_key])
                rendered.add(type_key)
        for type_key in sorted(groups):
            if type_key not in rendered:
                self._render_group(lines, type_key, groups[type_key])

        return "\n".join(lines).rstrip()

    @staticmethod
    def _render_group(lines: list[str], type_key: str, entries: list[ChangelogEntry]) -> None:
        lines.append(f"### {type_key.capitalize()}")
        for entry in entries:
            pr_suffix = f" ({entry.pr_url})" if entry.pr_url else ""
            lines.append(f"- {entry.message}{pr_suffix}")
        lines.append("")
