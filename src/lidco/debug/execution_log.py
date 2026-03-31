"""Q133: Structured execution log with filtering."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

_LEVELS = {"debug", "info", "warning", "error"}


@dataclass
class LogEntry:
    id: str
    level: str
    message: str
    source: str = ""
    timestamp: float = 0.0
    data: dict = field(default_factory=dict)


class ExecutionLog:
    """Bounded structured log with level/source/time filtering."""

    def __init__(self, max_entries: int = 1000) -> None:
        self._max = max_entries
        self._entries: list[LogEntry] = []

    # --- write ---------------------------------------------------------------

    def log(
        self,
        level: str,
        message: str,
        source: str = "",
        data: dict | None = None,
    ) -> LogEntry:
        entry = LogEntry(
            id=str(uuid.uuid4()),
            level=level.lower(),
            message=message,
            source=source,
            timestamp=time.time(),
            data=dict(data) if data else {},
        )
        self._entries.append(entry)
        if len(self._entries) > self._max:
            self._entries = self._entries[-self._max:]
        return entry

    def debug(self, msg: str, **kw) -> LogEntry:
        return self.log("debug", msg, **kw)

    def info(self, msg: str, **kw) -> LogEntry:
        return self.log("info", msg, **kw)

    def warning(self, msg: str, **kw) -> LogEntry:
        return self.log("warning", msg, **kw)

    def error(self, msg: str, **kw) -> LogEntry:
        return self.log("error", msg, **kw)

    # --- read ----------------------------------------------------------------

    def filter(
        self,
        level: str | None = None,
        source: str | None = None,
        since: float | None = None,
    ) -> list[LogEntry]:
        result = self._entries
        if level is not None:
            result = [e for e in result if e.level == level.lower()]
        if source is not None:
            result = [e for e in result if e.source == source]
        if since is not None:
            result = [e for e in result if e.timestamp >= since]
        return result

    def tail(self, n: int = 20) -> list[LogEntry]:
        return self._entries[-n:]

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
