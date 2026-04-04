"""HistorySearch — full-text search across commit messages, diffs, authors."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class SearchCommit:
    """Commit record used by HistorySearch."""

    hash: str
    message: str
    diff: str
    author: str
    date: datetime


@dataclass(frozen=True)
class SearchResult:
    """A single search hit."""

    hash: str
    author: str
    date: datetime
    message: str
    match_context: str = ""


class HistorySearch:
    """Full-text search over git history (messages, diffs, authors, dates)."""

    def __init__(self) -> None:
        self._commits: list[SearchCommit] = []

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def add_commit(
        self,
        hash: str,
        message: str,
        diff: str,
        author: str,
        date: datetime,
    ) -> None:
        """Add a commit to the searchable index."""
        self._commits.append(
            SearchCommit(hash=hash, message=message, diff=diff, author=author, date=date)
        )

    @property
    def count(self) -> int:
        return len(self._commits)

    # ------------------------------------------------------------------
    # Search methods
    # ------------------------------------------------------------------

    def search_messages(self, query: str) -> list[SearchResult]:
        """Search commit messages for *query* (case-insensitive substring)."""
        q = query.lower()
        results: list[SearchResult] = []
        for c in self._commits:
            if q in c.message.lower():
                results.append(
                    SearchResult(
                        hash=c.hash,
                        author=c.author,
                        date=c.date,
                        message=c.message,
                        match_context=c.message,
                    )
                )
        return results

    def search_diffs(self, pattern: str) -> list[SearchResult]:
        """Search commit diffs using a regex *pattern*."""
        try:
            rx = re.compile(pattern, re.IGNORECASE)
        except re.error:
            return []
        results: list[SearchResult] = []
        for c in self._commits:
            m = rx.search(c.diff)
            if m:
                results.append(
                    SearchResult(
                        hash=c.hash,
                        author=c.author,
                        date=c.date,
                        message=c.message,
                        match_context=m.group(0),
                    )
                )
        return results

    def by_author(self, author: str) -> list[SearchResult]:
        """Return all commits by *author* (case-insensitive substring)."""
        a = author.lower()
        results: list[SearchResult] = []
        for c in self._commits:
            if a in c.author.lower():
                results.append(
                    SearchResult(
                        hash=c.hash,
                        author=c.author,
                        date=c.date,
                        message=c.message,
                    )
                )
        return results

    def by_date_range(self, start: datetime, end: datetime) -> list[SearchResult]:
        """Return commits within the given date range (inclusive)."""
        results: list[SearchResult] = []
        for c in self._commits:
            if start <= c.date <= end:
                results.append(
                    SearchResult(
                        hash=c.hash,
                        author=c.author,
                        date=c.date,
                        message=c.message,
                    )
                )
        return results

    def combined(self, filters: dict[str, Any]) -> list[SearchResult]:
        """Apply multiple filters: message, diff, author, start_date, end_date.

        Returns the intersection of all specified filters.
        """
        candidate_hashes: set[str] | None = None

        def _intersect(results: list[SearchResult]) -> None:
            nonlocal candidate_hashes
            hashes = {r.hash for r in results}
            if candidate_hashes is None:
                candidate_hashes = hashes
            else:
                candidate_hashes &= hashes

        if "message" in filters:
            _intersect(self.search_messages(filters["message"]))
        if "diff" in filters:
            _intersect(self.search_diffs(filters["diff"]))
        if "author" in filters:
            _intersect(self.by_author(filters["author"]))
        if "start_date" in filters and "end_date" in filters:
            _intersect(self.by_date_range(filters["start_date"], filters["end_date"]))

        if candidate_hashes is None:
            return []

        # Return full results preserving commit order
        results: list[SearchResult] = []
        for c in self._commits:
            if c.hash in candidate_hashes:
                results.append(
                    SearchResult(
                        hash=c.hash,
                        author=c.author,
                        date=c.date,
                        message=c.message,
                    )
                )
        return results
