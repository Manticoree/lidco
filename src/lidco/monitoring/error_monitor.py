"""Error Monitor — watch log streams for error patterns and trigger callbacks (stdlib only).

Inspired by Sentry's local error capture: register patterns, feed lines
from log files or stderr, and receive structured error events.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class MonitorError(Exception):
    """Raised when the monitor cannot complete an operation."""


class Severity(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ErrorPattern:
    """A pattern to watch for in log output."""

    id: str
    pattern: str
    severity: Severity = Severity.ERROR
    description: str = ""
    tags: list[str] = field(default_factory=list)

    def compile(self) -> re.Pattern:
        return re.compile(self.pattern)


@dataclass
class ErrorEvent:
    """A captured error event from monitored output."""

    pattern_id: str
    matched_text: str
    line: str
    severity: Severity
    timestamp: float = field(default_factory=time.time)
    source: str = ""
    context: dict[str, Any] = field(default_factory=dict)

    def age_seconds(self) -> float:
        return time.time() - self.timestamp

    def format(self) -> str:
        ts = time.strftime("%H:%M:%S", time.localtime(self.timestamp))
        return f"[{ts}] [{self.severity.value.upper()}] {self.matched_text!r} — {self.line.strip()}"


ErrorHandler = Callable[[ErrorEvent], None]


class ErrorMonitor:
    """Register patterns and scan log lines for matching errors.

    Usage::

        monitor = ErrorMonitor()
        monitor.add_pattern(ErrorPattern("exc", r"Exception|Error", Severity.ERROR))

        @monitor.on_error("exc")
        def handle(event):
            print(f"Caught: {event.format()}")

        monitor.feed_line("Traceback ... ValueError: bad input")
        events = monitor.events()
    """

    def __init__(self, max_events: int = 1000) -> None:
        self._patterns: dict[str, ErrorPattern] = {}
        self._compiled: dict[str, re.Pattern] = {}
        self._handlers: dict[str, list[ErrorHandler]] = {}
        self._global_handlers: list[ErrorHandler] = []
        self._events: list[ErrorEvent] = []
        self._max_events = max_events

    # ------------------------------------------------------------------ #
    # Pattern management                                                   #
    # ------------------------------------------------------------------ #

    def add_pattern(self, pattern: ErrorPattern) -> None:
        if not pattern.id:
            raise MonitorError("Pattern id must not be empty")
        try:
            self._compiled[pattern.id] = pattern.compile()
        except re.error as exc:
            raise MonitorError(f"Invalid pattern regex: {exc}") from exc
        self._patterns[pattern.id] = pattern

    def remove_pattern(self, pattern_id: str) -> bool:
        if pattern_id not in self._patterns:
            return False
        del self._patterns[pattern_id]
        del self._compiled[pattern_id]
        self._handlers.pop(pattern_id, None)
        return True

    def list_patterns(self) -> list[ErrorPattern]:
        return list(self._patterns.values())

    # ------------------------------------------------------------------ #
    # Handler registration                                                 #
    # ------------------------------------------------------------------ #

    def on_error(self, pattern_id: str) -> Callable[[ErrorHandler], ErrorHandler]:
        """Decorator: register handler for a specific pattern."""
        def decorator(fn: ErrorHandler) -> ErrorHandler:
            self._handlers.setdefault(pattern_id, []).append(fn)
            return fn
        return decorator

    def add_handler(self, pattern_id: str, handler: ErrorHandler) -> None:
        self._handlers.setdefault(pattern_id, []).append(handler)

    def add_global_handler(self, handler: ErrorHandler) -> None:
        """Handler invoked for every matched event regardless of pattern."""
        self._global_handlers.append(handler)

    # ------------------------------------------------------------------ #
    # Feeding                                                              #
    # ------------------------------------------------------------------ #

    def feed_line(self, line: str, source: str = "") -> list[ErrorEvent]:
        """Process a single log line. Returns events triggered."""
        triggered: list[ErrorEvent] = []
        for pid, compiled in self._compiled.items():
            m = compiled.search(line)
            if m:
                pattern = self._patterns[pid]
                event = ErrorEvent(
                    pattern_id=pid,
                    matched_text=m.group(0),
                    line=line,
                    severity=pattern.severity,
                    source=source,
                )
                self._store_event(event)
                triggered.append(event)
                for handler in self._handlers.get(pid, []):
                    handler(event)
                for handler in self._global_handlers:
                    handler(event)
        return triggered

    def feed_lines(self, lines: list[str], source: str = "") -> list[ErrorEvent]:
        """Process multiple lines. Returns all triggered events."""
        all_events: list[ErrorEvent] = []
        for line in lines:
            all_events.extend(self.feed_line(line, source=source))
        return all_events

    def feed_file(self, path: Path | str) -> list[ErrorEvent]:
        """Read a file and process each line."""
        p = Path(path)
        if not p.exists():
            raise MonitorError(f"File not found: {path}")
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        return self.feed_lines(lines, source=str(path))

    # ------------------------------------------------------------------ #
    # Event store                                                          #
    # ------------------------------------------------------------------ #

    def _store_event(self, event: ErrorEvent) -> None:
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

    def events(
        self,
        pattern_id: str | None = None,
        severity: Severity | None = None,
        limit: int | None = None,
    ) -> list[ErrorEvent]:
        result = list(self._events)
        if pattern_id:
            result = [e for e in result if e.pattern_id == pattern_id]
        if severity:
            result = [e for e in result if e.severity == severity]
        if limit:
            result = result[-limit:]
        return result

    def clear_events(self) -> None:
        self._events.clear()

    def event_count(self) -> int:
        return len(self._events)

    # ------------------------------------------------------------------ #
    # Built-in defaults                                                    #
    # ------------------------------------------------------------------ #

    @classmethod
    def with_defaults(cls) -> "ErrorMonitor":
        """Return a monitor pre-loaded with common Python error patterns."""
        monitor = cls()
        patterns = [
            ErrorPattern("traceback", r"Traceback \(most recent call last\)",
                         Severity.ERROR, "Python traceback start", ["python"]),
            ErrorPattern("exception", r"\b(?:Exception|Error|Warning):\s*.+",
                         Severity.ERROR, "Generic exception line", ["python"]),
            ErrorPattern("syntax-error", r"SyntaxError:",
                         Severity.CRITICAL, "Python syntax error", ["python"]),
            ErrorPattern("import-error", r"ImportError:|ModuleNotFoundError:",
                         Severity.ERROR, "Missing module", ["python", "import"]),
            ErrorPattern("type-error", r"TypeError:",
                         Severity.ERROR, "Type mismatch", ["python"]),
            ErrorPattern("key-error", r"KeyError:",
                         Severity.WARNING, "Missing dict key", ["python"]),
            ErrorPattern("http-error", r"HTTP [45]\d\d",
                         Severity.ERROR, "HTTP client/server error", ["http"]),
            ErrorPattern("oom", r"MemoryError|Out of memory|OOM",
                         Severity.CRITICAL, "Out of memory", ["system"]),
        ]
        for p in patterns:
            monitor.add_pattern(p)
        return monitor

    def summary(self) -> dict[str, int]:
        """Return count of events grouped by severity."""
        counts: dict[str, int] = {}
        for event in self._events:
            counts[event.severity.value] = counts.get(event.severity.value, 0) + 1
        return counts
