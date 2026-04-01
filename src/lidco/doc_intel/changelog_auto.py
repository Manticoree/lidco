"""Auto-generate changelog from commit messages."""
from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import Any


class ChangeType(str, enum.Enum):
    """Conventional commit types."""

    FEAT = "feat"
    FIX = "fix"
    REFACTOR = "refactor"
    DOCS = "docs"
    TEST = "test"
    CHORE = "chore"
    PERF = "perf"
    BREAKING = "breaking"


_TYPE_MAP: dict[str, ChangeType] = {t.value: t for t in ChangeType}

_COMMIT_RE = re.compile(
    r"^(?P<type>[a-z]+)"
    r"(?:\((?P<scope>[^)]*)\))?"
    r"(?P<bang>!)?"
    r":\s*(?P<desc>.+?)(?:\s*\(#(?P<pr>\d+)\))?\s*$",
    re.IGNORECASE,
)

_TYPE_LABELS: dict[ChangeType, str] = {
    ChangeType.FEAT: "Added",
    ChangeType.FIX: "Fixed",
    ChangeType.REFACTOR: "Changed",
    ChangeType.DOCS: "Documentation",
    ChangeType.TEST: "Tests",
    ChangeType.CHORE: "Chores",
    ChangeType.PERF: "Performance",
    ChangeType.BREAKING: "Breaking Changes",
}


@dataclass(frozen=True)
class ChangeEntry:
    """A single changelog entry parsed from a commit message."""

    type: ChangeType
    description: str
    scope: str = ""
    pr_number: str = ""
    author: str = ""


class ChangelogGenerator:
    """Parse conventional commits and generate changelogs."""

    def __init__(self) -> None:
        pass

    def parse_commit(self, message: str) -> ChangeEntry | None:
        """Parse a single conventional commit message.

        Returns ``None`` if the message does not match the pattern.
        """
        first_line = message.strip().split("\n", 1)[0]
        m = _COMMIT_RE.match(first_line)
        if m is None:
            return None
        raw_type = m.group("type").lower()
        ctype = _TYPE_MAP.get(raw_type)
        if ctype is None:
            return None
        if m.group("bang"):
            ctype = ChangeType.BREAKING
        return ChangeEntry(
            type=ctype,
            description=m.group("desc").strip(),
            scope=m.group("scope") or "",
            pr_number=m.group("pr") or "",
        )

    def parse_commits(self, messages: list[str]) -> list[ChangeEntry]:
        """Parse multiple commit messages, discarding non-matching ones."""
        entries: list[ChangeEntry] = []
        for msg in messages:
            entry = self.parse_commit(msg)
            if entry is not None:
                entries.append(entry)
        return entries

    def generate(self, entries: list[ChangeEntry], version: str = "Unreleased") -> str:
        """Generate a changelog in Keep-a-Changelog format."""
        grouped = self.group_by_type(entries)
        lines = [f"## [{version}]", ""]
        for ctype in ChangeType:
            label = _TYPE_LABELS.get(ctype, ctype.value.title())
            items = grouped.get(ctype.value, [])
            if not items:
                continue
            lines.append(f"### {label}")
            lines.append("")
            for entry in items:
                scope_str = f"**{entry.scope}**: " if entry.scope else ""
                pr_str = f" (#{entry.pr_number})" if entry.pr_number else ""
                lines.append(f"- {scope_str}{entry.description}{pr_str}")
            lines.append("")
        return "\n".join(lines)

    def group_by_type(self, entries: list[ChangeEntry]) -> dict[str, list[ChangeEntry]]:
        """Group entries by their type value."""
        result: dict[str, list[ChangeEntry]] = {}
        for entry in entries:
            result.setdefault(entry.type.value, []).append(entry)
        return result

    def summary(self, entries: list[ChangeEntry]) -> str:
        """One-line summary of entry counts by type."""
        grouped = self.group_by_type(entries)
        parts = [f"{len(v)} {k}" for k, v in sorted(grouped.items())]
        return ", ".join(parts) if parts else "No changes"
