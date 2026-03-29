"""SessionSummarizer — summarize conversation turns when threshold is exceeded.

Task 734: Q120.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional


@dataclass
class SummaryRecord:
    id: str
    summary_text: str
    covered_through_turn: int
    created_at: str


class SessionSummarizer:
    """Periodically summarize session turns using an injected summarize_fn."""

    def __init__(
        self,
        summarize_fn: Optional[Callable[[list[dict]], str]] = None,
        max_turns_before_summarize: int = 20,
    ) -> None:
        self._summarize_fn = summarize_fn
        self._max_turns = max_turns_before_summarize
        self._last_summary: Optional[SummaryRecord] = None
        self._last_covered: int = 0

    def update(self, turns: list[dict], force: bool = False) -> Optional[SummaryRecord]:
        """Summarize *turns* if threshold is met or *force* is True.

        Returns a SummaryRecord on success, None otherwise.
        """
        if self._summarize_fn is None:
            return None

        n = len(turns)

        # Don't re-summarize the same set of turns
        if not force and n <= self._last_covered:
            return None

        if not force and n < self._max_turns:
            return None

        try:
            text = self._summarize_fn(turns)
        except Exception:
            return None

        record = SummaryRecord(
            id=uuid.uuid4().hex[:12],
            summary_text=text,
            covered_through_turn=n,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._last_summary = record
        self._last_covered = n
        return record

    def get_last_summary(self) -> Optional[SummaryRecord]:
        return self._last_summary

    def inject_context(self) -> str:
        """Return a context string with the last summary, or '' if none."""
        if self._last_summary is None:
            return ""
        return self._last_summary.summary_text

    def clear(self) -> None:
        self._last_summary = None
        self._last_covered = 0
