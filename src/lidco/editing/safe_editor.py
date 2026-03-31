"""SafeEditor — file editing with automatic undo/redo support.

Stdlib only — no external deps.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from lidco.editing.edit_transaction import EditTransaction
from lidco.editing.undo_stack import UndoStack


@dataclass
class EditResult:
    """Result of a safe edit operation."""

    success: bool
    file_path: str
    transaction: Optional[EditTransaction]
    error: Optional[str]


class SafeEditor:
    """File editor with built-in undo/redo tracking.

    Parameters
    ----------
    undo_stack : UndoStack, optional
        Stack to track edits. Created automatically if not supplied.
    """

    def __init__(self, undo_stack: Optional[UndoStack] = None) -> None:
        self._stack = undo_stack if undo_stack is not None else UndoStack()

    @property
    def undo_stack(self) -> UndoStack:
        return self._stack

    def edit(
        self,
        file_path: str,
        new_content: str,
        read_fn: Optional[Callable[[str], str]] = None,
        write_fn: Optional[Callable[[str, str], None]] = None,
    ) -> EditResult:
        """Read old content, write new content, push to undo stack."""
        _read = read_fn or _default_read
        _write = write_fn or _default_write

        try:
            old_content = _read(file_path)
        except Exception as exc:
            return EditResult(success=False, file_path=file_path, transaction=None, error=str(exc))

        tx = EditTransaction(label=f"edit {file_path}")
        tx.add(file_path, "modify", old_content=old_content, new_content=new_content)

        try:
            _write(file_path, new_content)
        except Exception as exc:
            return EditResult(success=False, file_path=file_path, transaction=None, error=str(exc))

        self._stack.push(tx)
        return EditResult(success=True, file_path=file_path, transaction=tx, error=None)

    def create(
        self,
        file_path: str,
        content: str,
        write_fn: Optional[Callable[[str, str], None]] = None,
    ) -> EditResult:
        """Create a new file and push to undo stack."""
        _write = write_fn or _default_write

        tx = EditTransaction(label=f"create {file_path}")
        tx.add(file_path, "create", old_content=None, new_content=content)

        try:
            _write(file_path, content)
        except Exception as exc:
            return EditResult(success=False, file_path=file_path, transaction=None, error=str(exc))

        self._stack.push(tx)
        return EditResult(success=True, file_path=file_path, transaction=tx, error=None)

    def delete(
        self,
        file_path: str,
        read_fn: Optional[Callable[[str], str]] = None,
        delete_fn: Optional[Callable[[str], None]] = None,
    ) -> EditResult:
        """Delete a file and push to undo stack."""
        _read = read_fn or _default_read
        _delete = delete_fn or _default_delete

        try:
            old_content = _read(file_path)
        except Exception as exc:
            return EditResult(success=False, file_path=file_path, transaction=None, error=str(exc))

        tx = EditTransaction(label=f"delete {file_path}")
        tx.add(file_path, "delete", old_content=old_content, new_content=None)

        try:
            _delete(file_path)
        except Exception as exc:
            return EditResult(success=False, file_path=file_path, transaction=None, error=str(exc))

        self._stack.push(tx)
        return EditResult(success=True, file_path=file_path, transaction=tx, error=None)

    def undo(self) -> Optional[EditResult]:
        """Undo the last transaction by applying rollback ops."""
        tx = self._stack.undo()
        if tx is None:
            return None

        rollback = tx.rollback_ops()
        errors: list[str] = []
        for op in rollback:
            try:
                if op.op_type == "delete":
                    _default_delete(op.file_path)
                elif op.op_type == "create":
                    _default_write(op.file_path, op.new_content or "")
                else:  # modify
                    _default_write(op.file_path, op.new_content or "")
            except Exception as exc:
                errors.append(f"{op.file_path}: {exc}")

        if errors:
            return EditResult(
                success=False,
                file_path=rollback[0].file_path if rollback else "",
                transaction=tx,
                error="; ".join(errors),
            )
        return EditResult(
            success=True,
            file_path=rollback[0].file_path if rollback else "",
            transaction=tx,
            error=None,
        )

    def redo(self) -> Optional[EditResult]:
        """Redo the last undone transaction."""
        tx = self._stack.redo()
        if tx is None:
            return None

        errors: list[str] = []
        for op in tx.operations:
            try:
                if op.op_type == "delete":
                    _default_delete(op.file_path)
                elif op.op_type == "create":
                    _default_write(op.file_path, op.new_content or "")
                else:  # modify
                    _default_write(op.file_path, op.new_content or "")
            except Exception as exc:
                errors.append(f"{op.file_path}: {exc}")

        if errors:
            return EditResult(
                success=False,
                file_path=tx.operations[0].file_path if tx.operations else "",
                transaction=tx,
                error="; ".join(errors),
            )
        return EditResult(
            success=True,
            file_path=tx.operations[0].file_path if tx.operations else "",
            transaction=tx,
            error=None,
        )

    def preview_next_undo(self) -> Optional[str]:
        """Show a summary of what the next undo would do."""
        tx = self._stack.peek_undo()
        if tx is None:
            return None
        rollback = tx.rollback_ops()
        lines = [f"Undo: {tx.label}"]
        for op in rollback:
            lines.append(f"  {op.op_type} {op.file_path}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Default I/O helpers
# ---------------------------------------------------------------------------


def _default_read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _default_write(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def _default_delete(path: str) -> None:
    import os

    os.remove(path)
