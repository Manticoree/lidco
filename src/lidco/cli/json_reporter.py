"""JSON output formatter for lidco exec --json — Task 262.

Produces a single JSON object on stdout describing the complete execution:

  {
    "session_id": "abc123",
    "task": "fix all failing tests",
    "status": "success",
    "exit_code": 0,
    "duration_s": 45.2,
    "cost_usd": 0.042,
    "tokens": {"prompt": 1200, "completion": 340, "total": 1540},
    "tool_calls": 12,
    "changes": [
      {"file": "src/foo.py", "action": "edit", "lines_added": 3, "lines_removed": 1}
    ],
    "output": "I fixed the failing tests by ...",
    "error": null
  }
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class FileChange:
    """Describes a single file mutation during exec."""
    file: str
    action: str           # "write" | "edit"
    lines_added: int = 0
    lines_removed: int = 0


@dataclass
class ExecResult:
    """Full result of a headless execution."""
    session_id: str
    task: str
    status: str           # "success" | "failed" | "timeout" | "permission_denied"
    exit_code: int
    duration_s: float
    cost_usd: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    tool_calls: int
    changes: list[FileChange]
    output: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Nest token counts
        d["tokens"] = {
            "prompt": d.pop("prompt_tokens"),
            "completion": d.pop("completion_tokens"),
            "total": d.pop("total_tokens"),
        }
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def print_json(self) -> None:
        """Write JSON to stdout."""
        print(self.to_json(), flush=True)


class ExecStats:
    """Mutable stats collector wired into orchestrator callbacks."""

    def __init__(self) -> None:
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.total_tokens: int = 0
        self.cost_usd: float = 0.0
        self.tool_calls: int = 0
        self.changes: list[FileChange] = []
        self._start: float = time.monotonic()

    def on_tokens(self, total: int, total_cost_usd: float = 0.0) -> None:
        self.total_tokens = total
        self.cost_usd = total_cost_usd

    def on_tool_event(
        self,
        event: str,
        tool_name: str,
        args: dict[str, Any],
        result: Any = None,
    ) -> None:
        if event == "tool_start":
            self.tool_calls += 1
        elif event == "tool_end":
            if tool_name in ("file_write", "file_edit"):
                file_path = args.get("path") or args.get("file_path", "")
                action = "write" if tool_name == "file_write" else "edit"
                change = FileChange(file=str(file_path), action=action)
                # Estimate line delta from diff if present in result
                if result and isinstance(result, str):
                    added = result.count("\n+") if "\n+" in result else 0
                    removed = result.count("\n-") if "\n-" in result else 0
                    change.lines_added = added
                    change.lines_removed = removed
                self.changes.append(change)

    def elapsed(self) -> float:
        return time.monotonic() - self._start
