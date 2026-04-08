"""ADR Manager — create and manage Architecture Decision Records.

Provides ``ADRManager`` for numbered ADR sequences with status tracking
(proposed/accepted/deprecated/superseded) and template-based creation.
"""

from __future__ import annotations

import copy
import enum
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class ADRStatus(enum.Enum):
    """Lifecycle status of an ADR."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


@dataclass
class ADR:
    """A single Architecture Decision Record."""

    number: int
    title: str
    status: ADRStatus = ADRStatus.PROPOSED
    context: str = ""
    decision: str = ""
    consequences: str = ""
    date: str = ""
    authors: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    superseded_by: int | None = None
    references: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.date:
            self.date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "number": self.number,
            "title": self.title,
            "status": self.status.value,
            "context": self.context,
            "decision": self.decision,
            "consequences": self.consequences,
            "date": self.date,
            "authors": list(self.authors),
            "tags": list(self.tags),
            "superseded_by": self.superseded_by,
            "references": list(self.references),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ADR:
        """Deserialise from a plain dict."""
        return ADR(
            number=int(data["number"]),
            title=str(data["title"]),
            status=ADRStatus(data.get("status", "proposed")),
            context=str(data.get("context", "")),
            decision=str(data.get("decision", "")),
            consequences=str(data.get("consequences", "")),
            date=str(data.get("date", "")),
            authors=list(data.get("authors", [])),
            tags=list(data.get("tags", [])),
            superseded_by=data.get("superseded_by"),
            references=list(data.get("references", [])),
        )

    def to_markdown(self) -> str:
        """Render to Markdown format."""
        lines: list[str] = []
        lines.append(f"# ADR-{self.number:04d}: {self.title}")
        lines.append("")
        lines.append(f"**Status:** {self.status.value}")
        lines.append(f"**Date:** {self.date}")
        if self.authors:
            lines.append(f"**Authors:** {', '.join(self.authors)}")
        if self.tags:
            lines.append(f"**Tags:** {', '.join(self.tags)}")
        if self.superseded_by is not None:
            lines.append(f"**Superseded by:** ADR-{self.superseded_by:04d}")
        lines.append("")
        lines.append("## Context")
        lines.append("")
        lines.append(self.context if self.context else "_No context provided._")
        lines.append("")
        lines.append("## Decision")
        lines.append("")
        lines.append(self.decision if self.decision else "_No decision recorded._")
        lines.append("")
        lines.append("## Consequences")
        lines.append("")
        lines.append(self.consequences if self.consequences else "_No consequences listed._")
        if self.references:
            lines.append("")
            lines.append("## References")
            lines.append("")
            for ref in self.references:
                lines.append(f"- {ref}")
        lines.append("")
        return "\n".join(lines)


_DEFAULT_TEMPLATE = (
    "# ADR-{number}: {title}\n\n"
    "**Status:** {status}\n"
    "**Date:** {date}\n\n"
    "## Context\n\n{context}\n\n"
    "## Decision\n\n{decision}\n\n"
    "## Consequences\n\n{consequences}\n"
)


@dataclass
class ADRTemplate:
    """Template for generating ADR markdown."""

    name: str
    content: str = _DEFAULT_TEMPLATE
    description: str = ""

    def render(self, adr: ADR) -> str:
        """Render the template with ADR data."""
        return self.content.format(
            number=f"{adr.number:04d}",
            title=adr.title,
            status=adr.status.value,
            date=adr.date,
            context=adr.context or "_No context provided._",
            decision=adr.decision or "_No decision recorded._",
            consequences=adr.consequences or "_No consequences listed._",
        )


class ADRManager:
    """Manage a collection of ADRs with numbered sequencing."""

    def __init__(self, base_dir: str = "") -> None:
        self._adrs: dict[int, ADR] = {}
        self._next_number: int = 1
        self._base_dir: str = base_dir
        self._templates: dict[str, ADRTemplate] = {
            "default": ADRTemplate(name="default", description="Standard ADR template"),
        }

    # -- Properties ----------------------------------------------------------

    @property
    def count(self) -> int:
        """Number of ADRs managed."""
        return len(self._adrs)

    @property
    def next_number(self) -> int:
        """Next ADR number in sequence."""
        return self._next_number

    @property
    def base_dir(self) -> str:
        return self._base_dir

    # -- CRUD ----------------------------------------------------------------

    def create(
        self,
        title: str,
        *,
        context: str = "",
        decision: str = "",
        consequences: str = "",
        authors: list[str] | None = None,
        tags: list[str] | None = None,
        status: ADRStatus = ADRStatus.PROPOSED,
        template_name: str = "default",
    ) -> ADR:
        """Create a new ADR with the next sequential number."""
        if not title.strip():
            raise ValueError("ADR title must not be empty")
        adr = ADR(
            number=self._next_number,
            title=title.strip(),
            status=status,
            context=context,
            decision=decision,
            consequences=consequences,
            authors=list(authors) if authors else [],
            tags=list(tags) if tags else [],
        )
        self._adrs[adr.number] = adr
        self._next_number += 1
        return adr

    def get(self, number: int) -> ADR | None:
        """Get an ADR by number."""
        return self._adrs.get(number)

    def list_all(self) -> list[ADR]:
        """List all ADRs sorted by number."""
        return sorted(self._adrs.values(), key=lambda a: a.number)

    def list_by_status(self, status: ADRStatus) -> list[ADR]:
        """List ADRs filtered by status."""
        return [a for a in self.list_all() if a.status == status]

    def update_status(self, number: int, status: ADRStatus) -> ADR:
        """Update the status of an ADR. Returns updated copy."""
        adr = self._adrs.get(number)
        if adr is None:
            raise KeyError(f"ADR-{number:04d} not found")
        updated = ADR(
            number=adr.number,
            title=adr.title,
            status=status,
            context=adr.context,
            decision=adr.decision,
            consequences=adr.consequences,
            date=adr.date,
            authors=list(adr.authors),
            tags=list(adr.tags),
            superseded_by=adr.superseded_by,
            references=list(adr.references),
        )
        self._adrs[number] = updated
        return updated

    def supersede(self, old_number: int, new_number: int) -> ADR:
        """Mark an ADR as superseded by another."""
        old = self._adrs.get(old_number)
        if old is None:
            raise KeyError(f"ADR-{old_number:04d} not found")
        if new_number not in self._adrs:
            raise KeyError(f"ADR-{new_number:04d} not found")
        updated = ADR(
            number=old.number,
            title=old.title,
            status=ADRStatus.SUPERSEDED,
            context=old.context,
            decision=old.decision,
            consequences=old.consequences,
            date=old.date,
            authors=list(old.authors),
            tags=list(old.tags),
            superseded_by=new_number,
            references=list(old.references),
        )
        self._adrs[old_number] = updated
        return updated

    def remove(self, number: int) -> ADR:
        """Remove an ADR by number."""
        adr = self._adrs.pop(number, None)
        if adr is None:
            raise KeyError(f"ADR-{number:04d} not found")
        return adr

    # -- Templates -----------------------------------------------------------

    def register_template(self, template: ADRTemplate) -> None:
        """Register a custom ADR template."""
        self._templates[template.name] = template

    def get_template(self, name: str) -> ADRTemplate | None:
        """Get a template by name."""
        return self._templates.get(name)

    def list_templates(self) -> list[str]:
        """List registered template names."""
        return sorted(self._templates.keys())

    # -- Export --------------------------------------------------------------

    def export_markdown(self, number: int, template_name: str = "default") -> str:
        """Export an ADR as markdown using a template."""
        adr = self._adrs.get(number)
        if adr is None:
            raise KeyError(f"ADR-{number:04d} not found")
        tmpl = self._templates.get(template_name)
        if tmpl is None:
            raise KeyError(f"Template '{template_name}' not found")
        return tmpl.render(adr)

    def export_all_markdown(self) -> dict[int, str]:
        """Export all ADRs as markdown."""
        return {num: self.export_markdown(num) for num in sorted(self._adrs)}
