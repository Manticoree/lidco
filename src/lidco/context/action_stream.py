"""ActionStreamBuffer — rolling buffer of recent agent actions as context."""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum


class ActionType(str, Enum):
    FILE_EDIT = "file_edit"
    TEST_RUN = "test_run"
    GIT_OP = "git_op"
    SHELL_CMD = "shell_cmd"
    FILE_READ = "file_read"
    OTHER = "other"


@dataclass
class ActionEvent:
    type: ActionType | str
    target: str
    summary: str
    timestamp: float = field(default_factory=time.time)

    def format_line(self) -> str:
        t = time.strftime("%H:%M:%S", time.localtime(self.timestamp))
        return f"[{t}] {self.type} {self.target}: {self.summary}"


class ActionStreamBuffer:
    """Ring buffer of recent agent actions, injectable as context."""

    def __init__(self, maxlen: int = 20) -> None:
        self._buffer: deque[ActionEvent] = deque(maxlen=maxlen)

    @property
    def maxlen(self) -> int:
        return self._buffer.maxlen  # type: ignore[return-value]

    def record(self, event: ActionEvent) -> None:
        self._buffer.append(event)

    def record_simple(self, type: ActionType | str, target: str, summary: str) -> None:
        self.record(ActionEvent(type=type, target=target, summary=summary))

    def format_context(self, limit: int = 10) -> str:
        events = list(self._buffer)[-limit:]
        if not events:
            return ""
        lines = [e.format_line() for e in events]
        return "## Recent activity\n" + "\n".join(lines)

    def clear(self) -> None:
        self._buffer.clear()

    def __len__(self) -> int:
        return len(self._buffer)

    def events(self) -> list[ActionEvent]:
        return list(self._buffer)
