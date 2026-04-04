"""PDF analysis module — simulated PDF text/table extraction.

PdfAnalyzer provides text extraction, table detection, spec parsing,
and summarisation for PDF documents.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TableInfo:
    """A table extracted from a PDF."""

    page: int
    rows: list[list[str]] = field(default_factory=list)
    header: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SpecSection:
    """A section parsed from a specification PDF."""

    title: str
    content: str
    page: int
    level: int = 1


class PdfAnalyzer:
    """Analyse PDF documents (simulated extraction)."""

    def __init__(self, *, max_pages: int = 100) -> None:
        self._max_pages = max_pages

    def extract_text(self, path: str, pages: str | None = None) -> str:
        """Extract text from a PDF, optionally for specific pages."""
        self._validate_path(path)
        page_range = self._parse_page_range(pages)
        # Simulated extraction
        base = os.path.splitext(os.path.basename(path))[0]
        lines: list[str] = []
        for p in page_range:
            lines.append(f"--- Page {p} ---")
            lines.append(f"Content of {base} page {p}.")
            lines.append(f"This is simulated text for page {p}.")
            lines.append("")
        return "\n".join(lines)

    def extract_tables(self, path: str) -> list[TableInfo]:
        """Extract tables from a PDF document."""
        self._validate_path(path)
        # Simulated table extraction
        return [
            TableInfo(
                page=1,
                header=["Column A", "Column B", "Column C"],
                rows=[
                    ["Row 1A", "Row 1B", "Row 1C"],
                    ["Row 2A", "Row 2B", "Row 2C"],
                ],
            ),
            TableInfo(
                page=2,
                header=["Name", "Value"],
                rows=[
                    ["alpha", "100"],
                    ["beta", "200"],
                ],
            ),
        ]

    def parse_spec(self, path: str) -> dict[str, Any]:
        """Parse a specification PDF into structured sections."""
        self._validate_path(path)
        base = os.path.splitext(os.path.basename(path))[0]
        sections = [
            SpecSection(title="Introduction", content=f"Overview of {base}.", page=1, level=1),
            SpecSection(title="Requirements", content="Functional and non-functional requirements.", page=2, level=1),
            SpecSection(title="Architecture", content="System architecture description.", page=3, level=1),
            SpecSection(title="API Reference", content="REST API endpoints and schemas.", page=5, level=2),
        ]
        return {
            "title": base.replace("_", " ").title(),
            "page_count": 10,
            "sections": [
                {"title": s.title, "content": s.content, "page": s.page, "level": s.level}
                for s in sections
            ],
        }

    def summary(self, path: str) -> str:
        """Generate a summary of the PDF content."""
        self._validate_path(path)
        base = os.path.splitext(os.path.basename(path))[0]
        title = base.replace("_", " ").title()
        tables = self.extract_tables(path)
        return (
            f"Summary of '{title}':\n"
            f"  Pages: ~10\n"
            f"  Tables found: {len(tables)}\n"
            f"  Key topics: introduction, requirements, architecture, API reference."
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_path(path: str) -> None:
        if not path:
            raise ValueError("path must not be empty")
        ext = os.path.splitext(path)[1].lower()
        if ext != ".pdf":
            raise ValueError(f"expected .pdf file, got: {ext or 'none'}")

    def _parse_page_range(self, pages: str | None) -> list[int]:
        """Parse a page range string like '1-5' or '3' into a list of page numbers."""
        if not pages:
            return list(range(1, min(self._max_pages, 11) + 1))
        parts = pages.strip().split("-")
        if len(parts) == 1:
            p = int(parts[0])
            return [p]
        start = int(parts[0])
        end = int(parts[1])
        return list(range(start, min(end, self._max_pages) + 1))
