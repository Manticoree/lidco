"""Structured report renderer for plain text and Markdown (Q139/830)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass
class ReportSection:
    """A titled section of a report."""

    title: str
    content: str
    level: int = 1


class _Divider:
    """Marker for a horizontal divider."""


class _KeyValue:
    """Key-value pair entry."""

    def __init__(self, key: str, value: str) -> None:
        self.key = key
        self.value = value


class _BulletList:
    """Bulleted list entry."""

    def __init__(self, items: list[str]) -> None:
        self.items = list(items)


_Entry = Union[ReportSection, _Divider, _KeyValue, _BulletList]


class ReportRenderer:
    """Build and render structured reports."""

    def __init__(self, title: str) -> None:
        self._title = title
        self._entries: list[_Entry] = []

    # -- builders ----------------------------------------------------------

    def add_section(self, title: str, content: str, level: int = 1) -> None:
        """Add a titled section."""
        self._entries.append(ReportSection(title=title, content=content, level=level))

    def add_key_value(self, key: str, value: object) -> None:
        """Add a key-value pair."""
        self._entries.append(_KeyValue(key=key, value=str(value)))

    def add_list(self, items: list[str]) -> None:
        """Add a bulleted list."""
        self._entries.append(_BulletList(items=items))

    def add_divider(self) -> None:
        """Add a horizontal divider."""
        self._entries.append(_Divider())

    # -- queries -----------------------------------------------------------

    def summary(self) -> str:
        """Return title and section count."""
        section_count = sum(1 for e in self._entries if isinstance(e, ReportSection))
        return f"{self._title} ({section_count} sections)"

    # -- renderers ---------------------------------------------------------

    def render(self) -> str:
        """Render as plain text."""
        lines: list[str] = []
        header = f"=== {self._title} ==="
        lines.append(header)
        lines.append("")

        for entry in self._entries:
            if isinstance(entry, ReportSection):
                indent = "  " * (entry.level - 1)
                lines.append(f"{indent}--- {entry.title} ---")
                for cline in entry.content.split("\n"):
                    lines.append(f"{indent}  {cline}")
                lines.append("")
            elif isinstance(entry, _KeyValue):
                lines.append(f"  {entry.key}: {entry.value}")
            elif isinstance(entry, _BulletList):
                for item in entry.items:
                    lines.append(f"  - {item}")
            elif isinstance(entry, _Divider):
                lines.append("-" * 40)
            lines_last = lines[-1] if lines else ""

        return "\n".join(lines)

    def render_markdown(self) -> str:
        """Render as Markdown."""
        lines: list[str] = []
        lines.append(f"# {self._title}")
        lines.append("")

        for entry in self._entries:
            if isinstance(entry, ReportSection):
                prefix = "#" * (entry.level + 1)
                lines.append(f"{prefix} {entry.title}")
                lines.append("")
                lines.append(entry.content)
                lines.append("")
            elif isinstance(entry, _KeyValue):
                lines.append(f"**{entry.key}:** {entry.value}")
            elif isinstance(entry, _BulletList):
                for item in entry.items:
                    lines.append(f"- {item}")
                lines.append("")
            elif isinstance(entry, _Divider):
                lines.append("---")
                lines.append("")

        return "\n".join(lines)
