"""Shared editing session state for collaborative editing."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EditOperation:
    """A single edit operation."""

    user_id: str
    op_type: str  # "insert" | "delete" | "replace"
    position: int
    content: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class EditorState:
    """Current state of the collaborative editor."""

    content: str = ""
    cursors: dict[str, int] = field(default_factory=dict)
    version: int = 0


class CollaborativeEditor:
    """Shared editing session with multi-user cursor tracking and undo."""

    def __init__(self, initial_content: str = "") -> None:
        self._state = EditorState(content=initial_content)
        self._history: list[EditOperation] = []
        self._user_ops: dict[str, list[tuple[int, str]]] = {}

    def apply(self, operation: EditOperation) -> EditorState:
        """Apply an edit operation and return the new state."""
        content = self._state.content
        pos = max(0, min(operation.position, len(content)))

        old_content = content

        if operation.op_type == "insert":
            content = content[:pos] + operation.content + content[pos:]
        elif operation.op_type == "delete":
            end = min(pos + max(len(operation.content), 1), len(content))
            content = content[:pos] + content[end:]
        elif operation.op_type == "replace":
            end = min(pos + max(len(operation.content), 1), len(content))
            content = content[:pos] + operation.content + content[end:]

        self._history.append(operation)
        self._state = EditorState(
            content=content,
            cursors=dict(self._state.cursors),
            version=self._state.version + 1,
        )

        # Track per-user ops for undo
        if operation.user_id not in self._user_ops:
            self._user_ops[operation.user_id] = []
        self._user_ops[operation.user_id].append(
            (self._state.version, old_content)
        )

        # Update cursor for this user
        if operation.op_type == "insert":
            self._state.cursors[operation.user_id] = pos + len(operation.content)
        else:
            self._state.cursors[operation.user_id] = pos

        return self.get_state()

    def get_state(self) -> EditorState:
        """Return current editor state."""
        return EditorState(
            content=self._state.content,
            cursors=dict(self._state.cursors),
            version=self._state.version,
        )

    def set_cursor(self, user_id: str, position: int) -> None:
        """Set cursor position for a user."""
        self._state.cursors[user_id] = position

    def get_cursor(self, user_id: str) -> int | None:
        """Get cursor position for a user, or None if not set."""
        return self._state.cursors.get(user_id)

    def undo(self, user_id: str) -> EditorState | None:
        """Undo the last operation by user_id."""
        ops = self._user_ops.get(user_id)
        if not ops:
            return None
        version, old_content = ops.pop()
        self._state = EditorState(
            content=old_content,
            cursors=dict(self._state.cursors),
            version=self._state.version + 1,
        )
        return self.get_state()

    def participants(self) -> list[str]:
        """Return list of users who have applied operations."""
        seen: list[str] = []
        for op in self._history:
            if op.user_id not in seen:
                seen.append(op.user_id)
        return seen

    def operation_history(self) -> list[EditOperation]:
        """Return the full operation history."""
        return list(self._history)
