"""Log rotation: archive records based on count or age policies."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import List

from lidco.logging.structured_logger import LogRecord


@dataclass
class RotationPolicy:
    """When to rotate logs."""

    max_records: int = 10000
    max_age_seconds: float = 86400


@dataclass
class RotatedArchive:
    """A snapshot of rotated log records."""

    id: str
    records: List[dict]
    created_at: float
    record_count: int


class LogRotator:
    """Rotate and archive log records per policy."""

    def __init__(self, policy: RotationPolicy | None = None) -> None:
        self._policy = policy or RotationPolicy()
        self._archives: list[RotatedArchive] = []

    # -- properties ----------------------------------------------------------

    @property
    def archives(self) -> list[RotatedArchive]:
        return list(self._archives)

    @property
    def total_archived(self) -> int:
        return sum(a.record_count for a in self._archives)

    # -- public API ----------------------------------------------------------

    def should_rotate(self, records: list, oldest_timestamp: float) -> bool:
        if len(records) >= self._policy.max_records:
            return True
        if oldest_timestamp > 0 and (time.time() - oldest_timestamp) >= self._policy.max_age_seconds:
            return True
        return False

    def rotate(self, records: list[LogRecord]) -> RotatedArchive:
        """Archive *records* and return the archive."""
        serialised = [
            {
                "level": r.level,
                "message": r.message,
                "timestamp": r.timestamp,
                "logger_name": r.logger_name,
                "context": r.context,
                "correlation_id": r.correlation_id,
            }
            for r in records
        ]
        archive = RotatedArchive(
            id=uuid.uuid4().hex[:12],
            records=serialised,
            created_at=time.time(),
            record_count=len(records),
        )
        self._archives.append(archive)
        return archive

    def cleanup(self, max_archives: int = 5) -> None:
        """Remove oldest archives beyond *max_archives*."""
        while len(self._archives) > max_archives:
            self._archives.pop(0)
