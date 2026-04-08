"""ADR Search — search and cross-reference Architecture Decision Records.

Full-text search, status/date/topic filtering, code cross-referencing,
and traceability support.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from lidco.adr.manager import ADR, ADRManager, ADRStatus


@dataclass
class SearchResult:
    """A single search hit."""

    adr: ADR
    score: float = 0.0
    matched_fields: list[str] = field(default_factory=list)
    snippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.adr.number,
            "title": self.adr.title,
            "score": self.score,
            "matched_fields": list(self.matched_fields),
            "snippet": self.snippet,
        }


@dataclass
class CodeReference:
    """A reference from code to an ADR."""

    file_path: str
    line_number: int
    adr_number: int
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "adr_number": self.adr_number,
            "text": self.text,
        }


@dataclass
class TraceabilityReport:
    """Traceability report linking ADRs to code references."""

    adr_number: int
    title: str
    status: str
    code_references: list[CodeReference] = field(default_factory=list)
    referenced_in_code: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "adr_number": self.adr_number,
            "title": self.title,
            "status": self.status,
            "code_references": [r.to_dict() for r in self.code_references],
            "referenced_in_code": self.referenced_in_code,
        }


# Pattern that matches ADR references in code (e.g., "ADR-0001", "adr-1", "ADR 42")
_ADR_REF_PATTERN = re.compile(r'\bADR[-\s]?(\d+)\b', re.IGNORECASE)


def _text_match_score(query: str, text: str) -> float:
    """Score how well query matches text (simple TF-based)."""
    if not query or not text:
        return 0.0
    query_lower = query.lower()
    text_lower = text.lower()
    # Exact substring match
    if query_lower in text_lower:
        return 1.0
    # Word overlap
    query_words = set(query_lower.split())
    text_words = set(text_lower.split())
    if not query_words:
        return 0.0
    overlap = query_words & text_words
    return len(overlap) / len(query_words)


class ADRSearch:
    """Search engine for Architecture Decision Records."""

    def __init__(self, manager: ADRManager) -> None:
        self._manager = manager

    @property
    def manager(self) -> ADRManager:
        return self._manager

    def full_text_search(self, query: str, *, limit: int = 20) -> list[SearchResult]:
        """Full-text search across all ADR fields."""
        if not query.strip():
            return []
        results: list[SearchResult] = []
        for adr in self._manager.list_all():
            total_score = 0.0
            matched: list[str] = []
            snippet = ""

            fields = {
                "title": adr.title,
                "context": adr.context,
                "decision": adr.decision,
                "consequences": adr.consequences,
            }
            for fname, fvalue in fields.items():
                score = _text_match_score(query, fvalue)
                if score > 0:
                    total_score += score
                    matched.append(fname)
                    if not snippet and fvalue:
                        # Extract snippet around match
                        idx = fvalue.lower().find(query.lower().split()[0])
                        start = max(0, idx - 30)
                        end = min(len(fvalue), idx + len(query) + 30)
                        snippet = fvalue[start:end]

            # Also check tags
            for tag in adr.tags:
                if query.lower() in tag.lower():
                    total_score += 0.5
                    matched.append("tags")
                    break

            if total_score > 0:
                results.append(SearchResult(
                    adr=adr,
                    score=round(total_score, 2),
                    matched_fields=matched,
                    snippet=snippet,
                ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def search_by_status(self, status: ADRStatus) -> list[SearchResult]:
        """Search ADRs by status."""
        return [
            SearchResult(adr=a, score=1.0, matched_fields=["status"])
            for a in self._manager.list_by_status(status)
        ]

    def search_by_date_range(
        self, start_date: str, end_date: str,
    ) -> list[SearchResult]:
        """Search ADRs within a date range (YYYY-MM-DD)."""
        results: list[SearchResult] = []
        for adr in self._manager.list_all():
            if start_date <= adr.date <= end_date:
                results.append(SearchResult(
                    adr=adr, score=1.0, matched_fields=["date"],
                ))
        return results

    def search_by_tag(self, tag: str) -> list[SearchResult]:
        """Search ADRs by tag."""
        tag_lower = tag.lower()
        results: list[SearchResult] = []
        for adr in self._manager.list_all():
            if any(t.lower() == tag_lower for t in adr.tags):
                results.append(SearchResult(
                    adr=adr, score=1.0, matched_fields=["tags"],
                ))
        return results

    def find_code_references(self, file_contents: dict[str, str]) -> list[CodeReference]:
        """Find ADR references in code files.

        Args:
            file_contents: mapping of file_path -> file content.

        Returns:
            List of CodeReference objects.
        """
        refs: list[CodeReference] = []
        for fpath, content in file_contents.items():
            for i, line in enumerate(content.splitlines(), 1):
                for match in _ADR_REF_PATTERN.finditer(line):
                    adr_num = int(match.group(1))
                    refs.append(CodeReference(
                        file_path=fpath,
                        line_number=i,
                        adr_number=adr_num,
                        text=line.strip(),
                    ))
        return refs

    def traceability_report(
        self, file_contents: dict[str, str] | None = None,
    ) -> list[TraceabilityReport]:
        """Generate traceability report for all ADRs.

        Args:
            file_contents: optional mapping of file_path -> content for
                cross-referencing.
        """
        code_refs = self.find_code_references(file_contents) if file_contents else []
        refs_by_num: dict[int, list[CodeReference]] = {}
        for ref in code_refs:
            refs_by_num.setdefault(ref.adr_number, []).append(ref)

        reports: list[TraceabilityReport] = []
        for adr in self._manager.list_all():
            adr_refs = refs_by_num.get(adr.number, [])
            reports.append(TraceabilityReport(
                adr_number=adr.number,
                title=adr.title,
                status=adr.status.value,
                code_references=adr_refs,
                referenced_in_code=len(adr_refs) > 0,
            ))
        return reports

    def cross_reference(self) -> dict[int, list[int]]:
        """Find cross-references between ADRs (based on references field)."""
        xrefs: dict[int, list[int]] = {}
        for adr in self._manager.list_all():
            related: list[int] = []
            # Check if any other ADR is mentioned in references
            for ref_text in adr.references:
                for match in _ADR_REF_PATTERN.finditer(ref_text):
                    num = int(match.group(1))
                    if num != adr.number and num not in related:
                        related.append(num)
            # Check superseded_by
            if adr.superseded_by is not None and adr.superseded_by not in related:
                related.append(adr.superseded_by)
            if related:
                xrefs[adr.number] = sorted(related)
        return xrefs
