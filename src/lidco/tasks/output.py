"""Task output streaming and filtering."""
from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class OutputLine:
    timestamp: float
    content: str
    stream: str = "stdout"
    task_id: str = ""


class TaskOutputManager:
    """Manage captured output lines from tasks."""

    def __init__(self, max_lines: int = 10000) -> None:
        self._max_lines = max_lines
        self._lines: dict[str, list[OutputLine]] = defaultdict(list)

    def append(self, task_id: str, content: str, stream: str = "stdout") -> None:
        line = OutputLine(
            timestamp=time.time(),
            content=content,
            stream=stream,
            task_id=task_id,
        )
        bucket = self._lines[task_id]
        bucket.append(line)
        if len(bucket) > self._max_lines:
            self._lines[task_id] = bucket[-self._max_lines :]

    def get_output(self, task_id: str, last_n: int | None = None) -> list[OutputLine]:
        bucket = self._lines.get(task_id, [])
        if last_n is not None:
            return bucket[-last_n:]
        return list(bucket)

    def tail(self, task_id: str, n: int = 20) -> list[OutputLine]:
        return self.get_output(task_id, last_n=n)

    def search(self, task_id: str, pattern: str) -> list[OutputLine]:
        bucket = self._lines.get(task_id, [])
        compiled = re.compile(pattern)
        return [line for line in bucket if compiled.search(line.content)]

    def export(self, task_id: str, format: str = "text") -> str:
        bucket = self._lines.get(task_id, [])
        if format == "json":
            items = [
                {
                    "timestamp": line.timestamp,
                    "content": line.content,
                    "stream": line.stream,
                    "task_id": line.task_id,
                }
                for line in bucket
            ]
            return json.dumps(items, indent=2)
        # text format
        return "\n".join(line.content for line in bucket)

    def clear(self, task_id: str) -> int:
        bucket = self._lines.pop(task_id, [])
        return len(bucket)

    def line_count(self, task_id: str) -> int:
        return len(self._lines.get(task_id, []))
