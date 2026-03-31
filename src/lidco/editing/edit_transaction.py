"""EditTransaction — group file operations into atomic units for undo/redo.

Stdlib only — no external deps.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EditOp:
    """A single file operation."""

    file_path: str
    op_type: str  # "create", "modify", "delete"
    old_content: Optional[str]
    new_content: Optional[str]
    timestamp: float = field(default_factory=time.time)


class EditTransaction:
    """A collection of EditOps representing one logical change.

    Parameters
    ----------
    label : str
        Human-readable label for this transaction.
    """

    def __init__(self, label: str = "") -> None:
        self.label = label
        self._operations: list[EditOp] = []
        self.timestamp: float = time.time()

    def add(
        self,
        file_path: str,
        op_type: str,
        old_content: Optional[str] = None,
        new_content: Optional[str] = None,
    ) -> None:
        """Add a file operation to this transaction."""
        self._operations.append(
            EditOp(
                file_path=file_path,
                op_type=op_type,
                old_content=old_content,
                new_content=new_content,
            )
        )

    @property
    def operations(self) -> list[EditOp]:
        """Return a copy of the operations list."""
        return list(self._operations)

    @property
    def is_empty(self) -> bool:
        return len(self._operations) == 0

    def rollback_ops(self) -> list[EditOp]:
        """Return reversed operations suitable for undo.

        - "create" → "delete" (swap old/new)
        - "modify" → "modify" with old/new swapped
        - "delete" → "create" (swap old/new)
        """
        result: list[EditOp] = []
        for op in reversed(self._operations):
            if op.op_type == "create":
                result.append(
                    EditOp(
                        file_path=op.file_path,
                        op_type="delete",
                        old_content=op.new_content,
                        new_content=op.old_content,
                    )
                )
            elif op.op_type == "delete":
                result.append(
                    EditOp(
                        file_path=op.file_path,
                        op_type="create",
                        old_content=op.new_content,
                        new_content=op.old_content,
                    )
                )
            else:  # modify
                result.append(
                    EditOp(
                        file_path=op.file_path,
                        op_type="modify",
                        old_content=op.new_content,
                        new_content=op.old_content,
                    )
                )
        return result

    def summary(self) -> str:
        """Human-readable summary, e.g. '3 files modified, 1 created'."""
        counts: dict[str, int] = {}
        for op in self._operations:
            counts[op.op_type] = counts.get(op.op_type, 0) + 1

        parts = []
        type_map = {"modify": "modified", "create": "created", "delete": "deleted"}
        for op_type in ("modify", "create", "delete"):
            count = counts.get(op_type, 0)
            if count > 0:
                word = "file" if count == 1 else "files"
                parts.append(f"{count} {word} {type_map[op_type]}")

        return ", ".join(parts) if parts else "no changes"

    def files_affected(self) -> list[str]:
        """Return deduplicated list of affected file paths (order preserved)."""
        seen: set[str] = set()
        result: list[str] = []
        for op in self._operations:
            if op.file_path not in seen:
                seen.add(op.file_path)
                result.append(op.file_path)
        return result
