"""UndoStack — bounded undo/redo stack for EditTransactions.

Stdlib only — no external deps.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from lidco.editing.edit_transaction import EditTransaction


@dataclass
class StackState:
    """Snapshot of the stack depths."""

    undo_depth: int
    redo_depth: int
    current_label: Optional[str]


class UndoStack:
    """Bounded undo/redo stack.

    Parameters
    ----------
    max_depth : int
        Maximum number of undo levels to keep. Oldest are discarded.
    """

    def __init__(self, max_depth: int = 50) -> None:
        self.max_depth = max_depth
        self._undo: list[EditTransaction] = []
        self._redo: list[EditTransaction] = []

    def push(self, transaction: EditTransaction) -> None:
        """Push a transaction onto the undo stack and clear redo."""
        self._undo.append(transaction)
        if len(self._undo) > self.max_depth:
            self._undo.pop(0)
        self._redo.clear()

    def undo(self) -> Optional[EditTransaction]:
        """Pop from undo, push to redo, return the transaction."""
        if not self._undo:
            return None
        tx = self._undo.pop()
        self._redo.append(tx)
        return tx

    def redo(self) -> Optional[EditTransaction]:
        """Pop from redo, push to undo, return the transaction."""
        if not self._redo:
            return None
        tx = self._redo.pop()
        self._undo.append(tx)
        return tx

    @property
    def can_undo(self) -> bool:
        return len(self._undo) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo) > 0

    def peek_undo(self) -> Optional[EditTransaction]:
        """View the top of the undo stack without popping."""
        if not self._undo:
            return None
        return self._undo[-1]

    def state(self) -> StackState:
        """Return current stack state."""
        label = self._undo[-1].label if self._undo else None
        return StackState(
            undo_depth=len(self._undo),
            redo_depth=len(self._redo),
            current_label=label,
        )

    def clear(self) -> None:
        """Clear both stacks."""
        self._undo.clear()
        self._redo.clear()
