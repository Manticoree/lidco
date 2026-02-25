"""Session error history — captures tool failures for debugger context."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone


def extract_file_hint(traceback_str: str | None) -> str | None:
    """Return the path of the first Python file mentioned in a traceback, or None."""
    if not traceback_str:
        return None
    m = re.search(r'File "([^"]+\.py)"', traceback_str)
    return m.group(1) if m else None


@dataclass(frozen=True)
class ErrorRecord:
    """An immutable record of a single tool failure during a session."""

    id: str                         # uuid4 hex
    timestamp: datetime             # UTC
    tool_name: str
    agent_name: str
    error_type: str                 # "tool_error" | "exception" | "timeout"
    message: str
    traceback_str: str | None
    file_hint: str | None           # first "File path.py" found in traceback


class ErrorHistory:
    """Ring buffer of recent ErrorRecords — thread-safe via immutable list swaps."""

    def __init__(self, max_size: int = 50) -> None:
        self._max_size = max_size
        self._records: list[ErrorRecord] = []

    def append(self, record: ErrorRecord) -> None:
        """Add *record* to the history, evicting the oldest entry if full."""
        new_records = self._records + [record]
        if len(new_records) > self._max_size:
            new_records = new_records[-self._max_size:]
        self._records = new_records

    def get_recent(self, n: int = 5) -> list[ErrorRecord]:
        """Return the *n* most recent records (oldest first)."""
        return self._records[-n:]

    def clear(self) -> None:
        """Remove all records."""
        self._records = []

    def __len__(self) -> int:
        return len(self._records)

    def to_context_str(self, n: int = 5) -> str:
        """Render the *n* most recent errors as a Markdown section for agent context.

        Returns an empty string when there are no errors.
        """
        recent = self.get_recent(n)
        if not recent:
            return ""

        lines: list[str] = ["## Recent Errors\n"]
        for rec in recent:
            ts = rec.timestamp.strftime("%H:%M:%S")
            msg_preview = rec.message[:120]
            lines.append(
                f"- **{ts}** `{rec.tool_name}` ({rec.agent_name}) [{rec.error_type}]: {msg_preview}"
            )
            if rec.file_hint:
                lines.append(f"  - File hint: `{rec.file_hint}`")
            if rec.traceback_str:
                tb_lines = [l for l in rec.traceback_str.splitlines() if l.strip()]
                last_five = tb_lines[-5:]
                tb_preview = "\n".join(f"    {l}" for l in last_five)
                lines.append(f"  - Traceback (last lines):\n```\n{tb_preview}\n```")

        return "\n".join(lines)
