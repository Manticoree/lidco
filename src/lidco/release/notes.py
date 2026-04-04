"""ReleaseNotesGenerator — human-readable release notes from changelog entries (stdlib only)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReleaseEntry:
    """A single entry for release notes generation."""

    type: str
    message: str
    author: str = ""
    breaking: bool = False


class ReleaseNotesGenerator:
    """Generate rich release notes from a list of :class:`ReleaseEntry` items."""

    # ------------------------------------------------------------------ #
    # Extraction helpers                                                   #
    # ------------------------------------------------------------------ #

    def highlights(self, entries: list[ReleaseEntry]) -> list[str]:
        """Return messages for entries of type ``added`` or ``changed``."""
        return [
            e.message
            for e in entries
            if e.type in ("added", "changed")
        ]

    def breaking_changes(self, entries: list[ReleaseEntry]) -> list[str]:
        """Return messages for entries marked as breaking."""
        return [e.message for e in entries if e.breaking]

    def contributors(self, entries: list[ReleaseEntry]) -> list[str]:
        """Return a deduplicated sorted list of authors."""
        seen: set[str] = set()
        result: list[str] = []
        for entry in entries:
            if entry.author and entry.author not in seen:
                seen.add(entry.author)
                result.append(entry.author)
        return sorted(result)

    def migration_guide(self, changes: list[str]) -> str:
        """Generate a migration guide from a list of breaking-change descriptions.

        Returns an empty string if there are no changes.
        """
        if not changes:
            return ""
        lines = ["## Migration Guide", ""]
        for i, change in enumerate(changes, 1):
            lines.append(f"{i}. {change}")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Full render                                                          #
    # ------------------------------------------------------------------ #

    def generate(self, version: str, entries: list[ReleaseEntry]) -> str:
        """Render complete release notes for *version*."""
        lines = [f"# Release {version}", ""]

        # Highlights
        hl = self.highlights(entries)
        if hl:
            lines.append("## Highlights")
            for item in hl:
                lines.append(f"- {item}")
            lines.append("")

        # Breaking changes
        bc = self.breaking_changes(entries)
        if bc:
            lines.append("## Breaking Changes")
            for item in bc:
                lines.append(f"- {item}")
            lines.append("")
            guide = self.migration_guide(bc)
            if guide:
                lines.append(guide)
                lines.append("")

        # Bug fixes
        fixes = [e.message for e in entries if e.type == "fixed"]
        if fixes:
            lines.append("## Bug Fixes")
            for item in fixes:
                lines.append(f"- {item}")
            lines.append("")

        # Contributors
        contribs = self.contributors(entries)
        if contribs:
            lines.append("## Contributors")
            for name in contribs:
                lines.append(f"- {name}")
            lines.append("")

        return "\n".join(lines).rstrip()
