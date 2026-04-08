"""Log Parser — parse structured/unstructured logs with auto-format detection.

Supports JSON, syslog, and custom formats with field extraction.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable


class LogFormat(Enum):
    """Supported log formats."""

    JSON = "json"
    SYSLOG = "syslog"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class LogEntry:
    """A single parsed log entry."""

    timestamp: str
    level: str
    message: str
    source: str = ""
    fields: dict[str, Any] = field(default_factory=dict)
    raw: str = ""
    line_number: int = 0
    format: LogFormat = LogFormat.UNKNOWN


@dataclass
class ParseResult:
    """Result of parsing a log source."""

    entries: list[LogEntry] = field(default_factory=list)
    format_detected: LogFormat = LogFormat.UNKNOWN
    total_lines: int = 0
    parsed_lines: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_lines == 0:
            return 0.0
        return self.parsed_lines / self.total_lines


# Syslog pattern: "Mon DD HH:MM:SS hostname process[pid]: message"
_SYSLOG_RE = re.compile(
    r"^(?P<timestamp>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<host>\S+)\s+"
    r"(?P<process>\S+?)(?:\[(?P<pid>\d+)\])?:\s+"
    r"(?P<message>.*)$"
)

# Common log level pattern
_LEVEL_RE = re.compile(
    r"\b(DEBUG|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL|TRACE)\b", re.IGNORECASE
)


class LogParser:
    """Parse structured and unstructured log lines with auto-format detection."""

    def __init__(self) -> None:
        self._custom_patterns: list[tuple[str, re.Pattern[str], list[str]]] = []

    def add_custom_pattern(
        self, name: str, pattern: str, field_names: list[str] | None = None
    ) -> None:
        """Register a custom regex pattern for parsing."""
        compiled = re.compile(pattern)
        names = field_names or list(compiled.groupindex.keys())
        self._custom_patterns.append((name, compiled, names))

    def detect_format(self, line: str) -> LogFormat:
        """Auto-detect the format of a single log line."""
        stripped = line.strip()
        if not stripped:
            return LogFormat.UNKNOWN
        # JSON?
        if stripped.startswith("{"):
            try:
                json.loads(stripped)
                return LogFormat.JSON
            except (json.JSONDecodeError, ValueError):
                pass
        # Custom patterns first (higher priority when registered)
        for _name, pat, _fields in self._custom_patterns:
            if pat.match(stripped):
                return LogFormat.CUSTOM
        # Syslog?
        if _SYSLOG_RE.match(stripped):
            return LogFormat.SYSLOG
        return LogFormat.UNKNOWN

    def parse_line(self, line: str, line_number: int = 0) -> LogEntry | None:
        """Parse a single log line. Returns *None* if unparseable."""
        stripped = line.strip()
        if not stripped:
            return None

        fmt = self.detect_format(stripped)

        if fmt == LogFormat.JSON:
            return self._parse_json(stripped, line_number)
        if fmt == LogFormat.CUSTOM:
            return self._parse_custom(stripped, line_number)
        if fmt == LogFormat.SYSLOG:
            return self._parse_syslog(stripped, line_number)

        # Best-effort: extract level + treat rest as message
        return self._parse_unknown(stripped, line_number)

    def parse(self, text: str) -> ParseResult:
        """Parse multi-line log text."""
        lines = text.splitlines()
        result = ParseResult(total_lines=len(lines))
        fmt_detected = LogFormat.UNKNOWN

        for idx, raw_line in enumerate(lines, start=1):
            if not raw_line.strip():
                continue
            entry = self.parse_line(raw_line, line_number=idx)
            if entry is not None:
                result.entries.append(entry)
                result.parsed_lines += 1
                if fmt_detected == LogFormat.UNKNOWN and entry.format != LogFormat.UNKNOWN:
                    fmt_detected = entry.format
            else:
                result.errors.append(f"Line {idx}: unparseable")

        result.format_detected = fmt_detected
        return result

    def extract_fields(self, entry: LogEntry, pattern: str) -> dict[str, str]:
        """Extract additional fields from a parsed entry's message via regex."""
        m = re.search(pattern, entry.message)
        if m:
            return m.groupdict()
        return {}

    # -- Private parsers ---------------------------------------------------

    def _parse_json(self, line: str, lineno: int) -> LogEntry | None:
        try:
            data = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            return None
        if not isinstance(data, dict):
            return None

        ts = str(data.get("timestamp", data.get("time", data.get("ts", ""))))
        level = str(data.get("level", data.get("severity", ""))).upper()
        msg = str(data.get("message", data.get("msg", "")))
        source = str(data.get("source", data.get("service", data.get("logger", ""))))
        extra = {k: v for k, v in data.items() if k not in {
            "timestamp", "time", "ts", "level", "severity",
            "message", "msg", "source", "service", "logger",
        }}
        return LogEntry(
            timestamp=ts, level=level, message=msg, source=source,
            fields=extra, raw=line, line_number=lineno, format=LogFormat.JSON,
        )

    def _parse_syslog(self, line: str, lineno: int) -> LogEntry | None:
        m = _SYSLOG_RE.match(line)
        if not m:
            return None
        level_match = _LEVEL_RE.search(m.group("message"))
        level = level_match.group(1).upper() if level_match else "INFO"
        extra: dict[str, Any] = {"host": m.group("host"), "process": m.group("process")}
        if m.group("pid"):
            extra["pid"] = m.group("pid")
        return LogEntry(
            timestamp=m.group("timestamp"), level=level, message=m.group("message"),
            source=m.group("process"), fields=extra, raw=line, line_number=lineno,
            format=LogFormat.SYSLOG,
        )

    def _parse_custom(self, line: str, lineno: int) -> LogEntry | None:
        for _name, pat, _field_names in self._custom_patterns:
            m = pat.match(line)
            if m:
                groups = m.groupdict()
                ts = groups.pop("timestamp", "")
                level = groups.pop("level", "").upper()
                msg = groups.pop("message", line)
                source = groups.pop("source", "")
                return LogEntry(
                    timestamp=ts, level=level, message=msg, source=source,
                    fields=groups, raw=line, line_number=lineno, format=LogFormat.CUSTOM,
                )
        return None

    def _parse_unknown(self, line: str, lineno: int) -> LogEntry:
        level_match = _LEVEL_RE.search(line)
        level = level_match.group(1).upper() if level_match else ""
        return LogEntry(
            timestamp="", level=level, message=line, raw=line,
            line_number=lineno, format=LogFormat.UNKNOWN,
        )
