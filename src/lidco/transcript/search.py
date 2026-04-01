"""Regex and fuzzy search with highlighting for transcripts."""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from lidco.transcript.store import TranscriptEntry, TranscriptStore


@dataclass(frozen=True)
class SearchMatch:
    """A single search match within a transcript entry."""

    entry: TranscriptEntry
    line_number: int
    match_start: int
    match_end: int
    context: str = ""


class TranscriptSearch:
    """Search engine for transcript entries."""

    def __init__(self, store: TranscriptStore) -> None:
        self._store = store

    def regex_search(
        self, pattern: str, role: str | None = None
    ) -> list[SearchMatch]:
        """Search entries using a regex pattern."""
        compiled = re.compile(pattern, re.IGNORECASE)
        matches: list[SearchMatch] = []
        for idx, entry in enumerate(self._store.list_entries(role=role)):
            for m in compiled.finditer(entry.content):
                matches.append(
                    SearchMatch(
                        entry=entry,
                        line_number=idx + 1,
                        match_start=m.start(),
                        match_end=m.end(),
                        context=entry.content[
                            max(0, m.start() - 30) : m.end() + 30
                        ],
                    )
                )
        return matches

    def fuzzy_search(
        self, query: str, threshold: float = 0.6
    ) -> list[SearchMatch]:
        """Fuzzy search using SequenceMatcher ratio."""
        matches: list[SearchMatch] = []
        query_lower = query.lower()
        for idx, entry in enumerate(self._store.list_entries()):
            ratio = SequenceMatcher(
                None, query_lower, entry.content.lower()
            ).ratio()
            if ratio >= threshold:
                matches.append(
                    SearchMatch(
                        entry=entry,
                        line_number=idx + 1,
                        match_start=0,
                        match_end=len(entry.content),
                        context=entry.content[:80],
                    )
                )
        return matches

    def highlight(self, text: str, pattern: str) -> str:
        """Wrap regex matches in **bold** markers."""
        def _repl(m: re.Match[str]) -> str:
            return f"**{m.group(0)}**"

        return re.sub(pattern, _repl, text, flags=re.IGNORECASE)

    def filter_by_time(
        self, start: float | None = None, end: float | None = None
    ) -> list[TranscriptEntry]:
        """Filter entries by timestamp range."""
        results: list[TranscriptEntry] = []
        for entry in self._store.list_entries():
            if start is not None and entry.timestamp < start:
                continue
            if end is not None and entry.timestamp > end:
                continue
            results.append(entry)
        return results

    def count_matches(self, pattern: str) -> int:
        """Count total regex matches across all entries."""
        compiled = re.compile(pattern, re.IGNORECASE)
        total = 0
        for entry in self._store.list_entries():
            total += len(compiled.findall(entry.content))
        return total
