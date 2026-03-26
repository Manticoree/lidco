"""Command pattern — Command protocol, SetValueCommand, DeleteKeyCommand, CommandHistory."""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

_UNSET = object()


@runtime_checkable
class Command(Protocol):
    description: str

    def execute(self) -> Any: ...
    def undo(self) -> None: ...


@dataclass
class SetValueCommand:
    """Concrete command: set ``target[key] = value``."""

    target: dict
    key: str
    value: Any
    description: str = ""

    _old_value: Any = field(default=_UNSET, init=False, repr=False)
    _had_key: bool = field(default=False, init=False, repr=False)

    def execute(self) -> Any:
        self._had_key = self.key in self.target
        self._old_value = self.target.get(self.key, _UNSET)
        self.target[self.key] = self.value
        return self._old_value if self._old_value is not _UNSET else None

    def undo(self) -> None:
        if self._had_key:
            self.target[self.key] = self._old_value
        else:
            self.target.pop(self.key, None)


@dataclass
class DeleteKeyCommand:
    """Concrete command: delete ``target[key]``."""

    target: dict
    key: str
    description: str = ""

    _old_value: Any = field(default=_UNSET, init=False, repr=False)
    _had_key: bool = field(default=False, init=False, repr=False)

    def execute(self) -> Any:
        self._had_key = self.key in self.target
        if self._had_key:
            self._old_value = self.target.pop(self.key)
            return self._old_value
        return None

    def undo(self) -> None:
        if self._had_key and self._old_value is not _UNSET:
            self.target[self.key] = self._old_value


class CommandHistory:
    """
    Undo/redo stack for Command objects.

    Parameters
    ----------
    max_history:
        Maximum number of commands in the undo stack.
    """

    def __init__(self, max_history: int = 100) -> None:
        self._undo_stack: collections.deque = collections.deque(maxlen=max_history)
        self._redo_stack: list[Command] = []

    def execute(self, cmd: Command) -> Any:
        """Execute *cmd*, push to undo stack, clear redo stack."""
        result = cmd.execute()
        self._undo_stack.append(cmd)
        self._redo_stack.clear()
        return result

    def undo(self) -> Command | None:
        """Undo the last command.  Return it, or None if stack is empty."""
        if not self._undo_stack:
            return None
        cmd = self._undo_stack.pop()
        cmd.undo()
        self._redo_stack.append(cmd)
        return cmd

    def redo(self) -> Command | None:
        """Redo the last undone command.  Return it, or None if stack is empty."""
        if not self._redo_stack:
            return None
        cmd = self._redo_stack.pop()
        cmd.execute()
        self._undo_stack.append(cmd)
        return cmd

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    @property
    def history(self) -> list[Command]:
        """Return a copy of the undo stack (oldest first)."""
        return list(self._undo_stack)

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
