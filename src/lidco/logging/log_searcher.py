"""Search and aggregate log records."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Tuple

from lidco.logging.structured_logger import LogRecord


@dataclass
class SearchQuery:
    """Filter criteria for log search."""

    text: Optional[str] = None
    level: Optional[str] = None
    logger_name: Optional[str] = None
    since: Optional[float] = None
    until: Optional[float] = None
    context_key: Optional[str] = None
    context_value: Optional[str] = None
    limit: int = 100


@dataclass
class SearchResult:
    """Outcome of a log search."""

    records: List[LogRecord]
    total_matched: int
    query: SearchQuery


class LogSearcher:
    """Query, count, and aggregate log records."""

    def search(self, records: list[LogRecord], query: SearchQuery) -> SearchResult:
        matched: list[LogRecord] = []
        for r in records:
            if not self._matches(r, query):
                continue
            matched.append(r)
        total = len(matched)
        limited = matched[: query.limit]
        return SearchResult(records=limited, total_matched=total, query=query)

    def count_by_level(self, records: list[LogRecord]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in records:
            counts[r.level] = counts.get(r.level, 0) + 1
        return counts

    def timeline(
        self, records: list[LogRecord], bucket_seconds: int = 3600
    ) -> list[tuple[float, int]]:
        """Bucket record counts by time intervals."""
        if not records:
            return []
        buckets: dict[float, int] = {}
        for r in records:
            key = (r.timestamp // bucket_seconds) * bucket_seconds
            buckets[key] = buckets.get(key, 0) + 1
        return sorted(buckets.items())

    def top_loggers(
        self, records: list[LogRecord], n: int = 5
    ) -> list[tuple[str, int]]:
        """Return the *n* most active loggers."""
        counts: dict[str, int] = {}
        for r in records:
            counts[r.logger_name] = counts.get(r.logger_name, 0) + 1
        return sorted(counts.items(), key=lambda x: x[1], reverse=True)[:n]

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _matches(record: LogRecord, query: SearchQuery) -> bool:
        if query.level is not None and record.level != query.level:
            return False
        if query.logger_name is not None and record.logger_name != query.logger_name:
            return False
        if query.text is not None and query.text.lower() not in record.message.lower():
            return False
        if query.since is not None and record.timestamp < query.since:
            return False
        if query.until is not None and record.timestamp > query.until:
            return False
        if query.context_key is not None:
            if query.context_key not in record.context:
                return False
            if query.context_value is not None:
                if str(record.context[query.context_key]) != query.context_value:
                    return False
        return True
