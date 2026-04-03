"""Conversation replay engine for stepping through and modifying message history."""
from __future__ import annotations


class ReplayEngine:
    """Navigate and modify a conversation message history."""

    def __init__(self, messages: list[dict]) -> None:
        self._messages: list[dict] = list(messages)
        self._cursor: int = -1

    @property
    def current_turn(self) -> int:
        """Return the current cursor position."""
        return self._cursor

    @property
    def total_turns(self) -> int:
        """Return the total number of messages."""
        return len(self._messages)

    def step_forward(self) -> dict | None:
        """Advance one turn and return the message, or None if at end."""
        next_pos = self._cursor + 1
        if next_pos >= len(self._messages):
            return None
        self._cursor = next_pos
        return dict(self._messages[self._cursor])

    def step_backward(self) -> dict | None:
        """Go back one turn and return the message, or None if at start."""
        prev_pos = self._cursor - 1
        if prev_pos < 0:
            return None
        self._cursor = prev_pos
        return dict(self._messages[self._cursor])

    def jump_to(self, turn: int) -> dict | None:
        """Jump to a specific turn index and return the message."""
        if turn < 0 or turn >= len(self._messages):
            return None
        self._cursor = turn
        return dict(self._messages[self._cursor])

    def modify_and_rerun(self, turn: int, new_message: dict) -> list[dict]:
        """Replace the message at *turn* and return all messages from that point."""
        if turn < 0 or turn >= len(self._messages):
            return []
        new_messages = list(self._messages)
        new_messages[turn] = dict(new_message)
        self._messages = new_messages
        self._cursor = turn
        return [dict(m) for m in self._messages[turn:]]

    def what_if(self, turn: int, alternative: dict) -> list[dict]:
        """Branch from *turn* with an alternative message, without mutating original."""
        if turn < 0 or turn >= len(self._messages):
            return []
        branch = [dict(m) for m in self._messages[:turn]]
        branch.append(dict(alternative))
        return branch

    def reset(self) -> None:
        """Reset the cursor to the beginning."""
        self._cursor = -1
