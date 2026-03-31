"""Structured logger with level filtering and immutable context."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Optional


LEVEL_ORDER = {"debug": 0, "info": 1, "warning": 2, "error": 3, "critical": 4}


@dataclass
class LogRecord:
    """A single structured log entry."""

    level: str
    message: str
    timestamp: float
    logger_name: str
    context: dict = field(default_factory=dict)
    correlation_id: Optional[str] = None


class StructuredLogger:
    """Logger that produces :class:`LogRecord` instances with level filtering."""

    def __init__(self, name: str, min_level: str = "debug") -> None:
        self._name = name
        self._min_level = min_level.lower()
        self._context: dict = {}
        self._correlation_id: Optional[str] = None
        self._records: list[LogRecord] = []

    # -- properties ----------------------------------------------------------

    @property
    def records(self) -> list[LogRecord]:
        return list(self._records)

    # -- public API ----------------------------------------------------------

    def clear(self) -> None:
        self._records.clear()

    def debug(self, msg: str, **ctx: object) -> None:
        self._log("debug", msg, ctx)

    def info(self, msg: str, **ctx: object) -> None:
        self._log("info", msg, ctx)

    def warning(self, msg: str, **ctx: object) -> None:
        self._log("warning", msg, ctx)

    def error(self, msg: str, **ctx: object) -> None:
        self._log("error", msg, ctx)

    def critical(self, msg: str, **ctx: object) -> None:
        self._log("critical", msg, ctx)

    def with_context(self, **ctx: object) -> StructuredLogger:
        """Return a new logger with merged context (immutable)."""
        new = StructuredLogger(self._name, self._min_level)
        new._context = {**self._context, **ctx}
        new._correlation_id = self._correlation_id
        new._records = self._records  # shared backing list
        return new

    def with_correlation(self, correlation_id: str) -> StructuredLogger:
        """Return a new logger with a correlation ID set."""
        new = StructuredLogger(self._name, self._min_level)
        new._context = dict(self._context)
        new._correlation_id = correlation_id
        new._records = self._records
        return new

    # -- formatting ----------------------------------------------------------

    @staticmethod
    def format_json(record: LogRecord) -> str:
        """Serialise *record* to a JSON string."""
        payload: dict = {
            "level": record.level,
            "message": record.message,
            "timestamp": record.timestamp,
            "logger": record.logger_name,
        }
        if record.context:
            payload["context"] = record.context
        if record.correlation_id is not None:
            payload["correlation_id"] = record.correlation_id
        return json.dumps(payload, default=str)

    @staticmethod
    def format_text(record: LogRecord) -> str:
        """Format *record* as ``[LEVEL] name: msg {ctx}``."""
        parts = [f"[{record.level.upper()}] {record.logger_name}: {record.message}"]
        if record.context:
            parts.append(f" {record.context}")
        return "".join(parts)

    # -- internals -----------------------------------------------------------

    _VALID_LEVELS = frozenset(LEVEL_ORDER)

    def _log(self, level: str, msg: str, extra: dict) -> None:
        if level not in self._VALID_LEVELS:
            raise ValueError(
                f"Invalid log level {level!r}. "
                f"Must be one of: {', '.join(sorted(self._VALID_LEVELS, key=lambda l: LEVEL_ORDER[l]))}"
            )
        if LEVEL_ORDER.get(level, 0) < LEVEL_ORDER.get(self._min_level, 0):
            return
        merged = {**self._context, **extra} if extra else dict(self._context)
        record = LogRecord(
            level=level,
            message=msg,
            timestamp=time.time(),
            logger_name=self._name,
            context=merged,
            correlation_id=self._correlation_id,
        )
        self._records.append(record)
