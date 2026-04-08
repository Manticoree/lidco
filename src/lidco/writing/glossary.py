"""Glossary Manager — Project glossary with auto-detection and consistency.

Manage term definitions, auto-detect undefined terms in text,
cross-reference related terms, and enforce consistency.  Pure stdlib.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GlossaryEntry:
    """A single glossary term."""

    term: str
    definition: str
    aliases: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    category: str = ""

    def matches(self, text: str) -> bool:
        """Check if this term or any alias appears in *text*."""
        lower = text.lower()
        if self.term.lower() in lower:
            return True
        return any(a.lower() in lower for a in self.aliases)


@dataclass(frozen=True)
class UndefinedTerm:
    """A term detected in text that has no glossary definition."""

    term: str
    line: int
    context: str  # surrounding text snippet


@dataclass(frozen=True)
class ConsistencyViolation:
    """A glossary consistency violation (alias used instead of canonical term)."""

    alias_used: str
    canonical: str
    line: int


@dataclass
class GlossaryReport:
    """Report from scanning text against the glossary."""

    defined_terms_found: list[str] = field(default_factory=list)
    undefined_terms: list[UndefinedTerm] = field(default_factory=list)
    consistency_violations: list[ConsistencyViolation] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Common technical terms for auto-detection
# ---------------------------------------------------------------------------

_COMMON_TECH_TERMS: set[str] = {
    "api", "sdk", "cli", "ci", "cd", "dns", "http", "https", "tcp", "udp",
    "rest", "grpc", "graphql", "websocket", "oauth", "jwt", "cors",
    "crud", "orm", "sql", "nosql", "redis", "kafka",
    "docker", "kubernetes", "terraform", "ansible",
    "microservice", "monolith", "serverless", "lambda",
    "mutex", "semaphore", "deadlock", "race condition",
    "idempotent", "idempotency", "eventual consistency",
    "sharding", "replication", "partitioning",
    "latency", "throughput", "availability", "scalability",
    "rollback", "migration", "schema", "index",
}

_WORD_RE = re.compile(r"\b[a-zA-Z][-a-zA-Z]{2,}\b")


# ---------------------------------------------------------------------------
# GlossaryManager
# ---------------------------------------------------------------------------

class GlossaryManager:
    """Project glossary with auto-detection and consistency enforcement."""

    def __init__(self) -> None:
        self._entries: dict[str, GlossaryEntry] = {}

    # -- CRUD ----------------------------------------------------------------

    def add(self, entry: GlossaryEntry) -> None:
        """Add or update a glossary entry."""
        self._entries[entry.term.lower()] = entry

    def remove(self, term: str) -> bool:
        """Remove an entry. Returns True if found."""
        key = term.lower()
        if key in self._entries:
            del self._entries[key]
            return True
        return False

    def get(self, term: str) -> GlossaryEntry | None:
        """Look up a term (case-insensitive)."""
        return self._entries.get(term.lower())

    def list_entries(self) -> list[GlossaryEntry]:
        """Return all entries sorted by term."""
        return sorted(self._entries.values(), key=lambda e: e.term.lower())

    def search(self, query: str) -> list[GlossaryEntry]:
        """Search entries by term, alias, or definition substring."""
        q = query.lower()
        results: list[GlossaryEntry] = []
        for entry in self._entries.values():
            if (
                q in entry.term.lower()
                or q in entry.definition.lower()
                or any(q in a.lower() for a in entry.aliases)
            ):
                results.append(entry)
        return sorted(results, key=lambda e: e.term.lower())

    @property
    def count(self) -> int:
        return len(self._entries)

    # -- Analysis ------------------------------------------------------------

    def scan(self, text: str) -> GlossaryReport:
        """Scan *text* for defined/undefined terms and consistency issues."""
        report = GlossaryReport()
        lines = text.splitlines()

        # Track which defined terms appear
        for entry in self._entries.values():
            if entry.matches(text):
                report.defined_terms_found.append(entry.term)

        # Check for alias usage (consistency violations)
        for lineno, line in enumerate(lines, start=1):
            lower = line.lower()
            for entry in self._entries.values():
                for alias in entry.aliases:
                    if alias.lower() in lower:
                        report.consistency_violations.append(
                            ConsistencyViolation(
                                alias_used=alias,
                                canonical=entry.term,
                                line=lineno,
                            )
                        )

        # Auto-detect potentially undefined technical terms
        defined_lower = set()
        for entry in self._entries.values():
            defined_lower.add(entry.term.lower())
            for a in entry.aliases:
                defined_lower.add(a.lower())

        for lineno, line in enumerate(lines, start=1):
            words = _WORD_RE.findall(line)
            for word in words:
                wl = word.lower()
                if wl in _COMMON_TECH_TERMS and wl not in defined_lower:
                    # Extract context
                    start = max(0, line.lower().find(wl) - 20)
                    end = min(len(line), line.lower().find(wl) + len(wl) + 20)
                    ctx = line[start:end].strip()
                    report.undefined_terms.append(
                        UndefinedTerm(term=word, line=lineno, context=ctx)
                    )

        return report

    def cross_references(self, term: str) -> list[GlossaryEntry]:
        """Get entries related to *term*."""
        entry = self.get(term)
        if entry is None:
            return []
        refs: list[GlossaryEntry] = []
        for related_term in entry.related:
            ref = self.get(related_term)
            if ref is not None:
                refs.append(ref)
        return refs

    # -- Persistence ---------------------------------------------------------

    def export_json(self) -> str:
        """Export glossary as JSON string."""
        data = []
        for entry in self.list_entries():
            data.append({
                "term": entry.term,
                "definition": entry.definition,
                "aliases": entry.aliases,
                "related": entry.related,
                "category": entry.category,
            })
        return json.dumps(data, indent=2)

    def import_json(self, raw: str) -> int:
        """Import entries from JSON string. Returns count of entries added."""
        data = json.loads(raw)
        count = 0
        for item in data:
            entry = GlossaryEntry(
                term=item["term"],
                definition=item["definition"],
                aliases=item.get("aliases", []),
                related=item.get("related", []),
                category=item.get("category", ""),
            )
            self.add(entry)
            count += 1
        return count
