"""Test-first enforcement — Task 291.

Monitors the agent's tool calls and warns when implementation code
is written before any test file.

Heuristics:
- A ``file_write`` or ``file_edit`` to ``src/`` / ``lib/`` / non-test path
  before writing to ``tests/`` is flagged.
- Resets per-turn so each user request is evaluated independently.

Usage::

    enforcer = TestFirstEnforcer()
    enforcer.on_tool_call("file_write", {"path": "src/auth.py", "content": "..."})
    if enforcer.has_violation():
        print(enforcer.violation_message())
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


_TEST_PATH_PATTERNS = re.compile(
    r"(^|/)tests?/|_test\.py$|test_[a-zA-Z]|spec[_/]|/spec\.py$",
    re.IGNORECASE,
)
_IMPL_PATH_PATTERNS = re.compile(
    r"(^|/)(src|lib|app|pkg)/.*\.py$|(?<!test_)[a-zA-Z0-9_]+\.py$",
    re.IGNORECASE,
)

_WRITE_TOOLS = frozenset({"file_write", "file_edit"})


@dataclass
class ViolationRecord:
    """A test-first violation event."""

    impl_path: str
    turn: int
    message: str


class TestFirstEnforcer:
    """Tracks file writes and flags when implementation precedes tests.

    Args:
        enabled: Whether enforcement is active (default: True).
        mode: "warn" (default) — log/return warning; "block" — raise exception.
    """

    def __init__(self, enabled: bool = True, mode: str = "warn") -> None:
        self._enabled = enabled
        self._mode = mode
        self._impl_written: list[str] = []
        self._tests_written: list[str] = []
        self._violations: list[ViolationRecord] = []
        self._turn: int = 0

    def reset_turn(self) -> None:
        """Call at the start of each new user turn."""
        self._impl_written = []
        self._tests_written = []
        self._turn += 1

    def on_tool_call(self, tool_name: str, args: dict) -> None:
        """Process a tool call event."""
        if not self._enabled:
            return
        if tool_name not in _WRITE_TOOLS:
            return
        path = args.get("path", "")
        if not path:
            return
        if _is_test_file(path):
            self._tests_written.append(path)
        elif _is_impl_file(path):
            self._impl_written.append(path)
            if not self._tests_written:
                msg = (
                    f"⚠️  Test-first violation: implementation written before tests.\n"
                    f"   File: `{path}`\n"
                    f"   Write tests first, then implement."
                )
                v = ViolationRecord(impl_path=path, turn=self._turn, message=msg)
                self._violations.append(v)
                if self._mode == "block":
                    raise TestFirstViolation(msg)

    def has_violation(self) -> bool:
        """Return True if a violation was recorded in the current turn."""
        return any(v.turn == self._turn for v in self._violations)

    def violation_message(self) -> str:
        """Return the latest violation message, or empty string."""
        current = [v for v in self._violations if v.turn == self._turn]
        return current[-1].message if current else ""

    def all_violations(self) -> list[ViolationRecord]:
        return list(self._violations)

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def set_mode(self, mode: str) -> None:
        """Set mode: 'warn' or 'block'."""
        if mode not in ("warn", "block"):
            raise ValueError(f"Invalid mode: {mode!r}")
        self._mode = mode


class TestFirstViolation(Exception):
    """Raised when mode='block' and impl is written before tests."""


def _is_test_file(path: str) -> bool:
    return bool(_TEST_PATH_PATTERNS.search(path))


def _is_impl_file(path: str) -> bool:
    return bool(_IMPL_PATH_PATTERNS.search(path)) and not _is_test_file(path)
