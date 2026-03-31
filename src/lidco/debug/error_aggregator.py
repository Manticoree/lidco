"""Q133: Error aggregator — group repeated errors and track counts."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ErrorRecord:
    id: str
    error_type: str
    message: str
    count: int = 1
    first_seen: float = 0.0
    last_seen: float = 0.0
    context: dict = field(default_factory=dict)


class ErrorAggregator:
    """Record and aggregate errors by (type, message)."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], ErrorRecord] = {}

    def record(self, error: Exception, context: dict | None = None) -> ErrorRecord:
        """Record *error*, incrementing count if already seen."""
        etype = type(error).__name__
        msg = str(error)
        key = (etype, msg)
        now = time.time()

        if key in self._records:
            rec = self._records[key]
            rec.count += 1
            rec.last_seen = now
            if context:
                rec.context.update(context)
            return rec

        rec = ErrorRecord(
            id=str(uuid.uuid4()),
            error_type=etype,
            message=msg,
            count=1,
            first_seen=now,
            last_seen=now,
            context=dict(context) if context else {},
        )
        self._records[key] = rec
        return rec

    def get_all(self) -> list[ErrorRecord]:
        return list(self._records.values())

    def top(self, n: int = 5) -> list[ErrorRecord]:
        """Return top *n* records by count (descending)."""
        return sorted(self._records.values(), key=lambda r: r.count, reverse=True)[:n]

    def since(self, timestamp: float) -> list[ErrorRecord]:
        """Return records where last_seen >= *timestamp*."""
        return [r for r in self._records.values() if r.last_seen >= timestamp]

    def clear(self) -> None:
        self._records.clear()

    def summary(self) -> dict:
        records = list(self._records.values())
        total_occurrences = sum(r.count for r in records)
        types: dict[str, int] = {}
        for r in records:
            types[r.error_type] = types.get(r.error_type, 0) + r.count
        return {
            "total_records": len(records),
            "total_occurrences": total_occurrences,
            "types": types,
        }
