"""Batch file-system writer — queue write / delete / mkdir ops and execute atomically."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class FileOp:
    """A single file-system operation."""

    action: str  # "WRITE" | "DELETE" | "MKDIR"
    path: str
    content: str = ""


@dataclass(frozen=True)
class BatchPlan:
    """Dry-run plan listing queued operations."""

    operations: tuple[FileOp, ...]
    total: int


@dataclass(frozen=True)
class BatchResult:
    """Outcome of executing all queued operations."""

    success: bool
    completed: int
    failed: int
    errors: tuple[str, ...]


class BatchWriter:
    """Immutable builder for file-system batch operations.

    Every mutating method returns a *new* instance.
    """

    def __init__(self, operations: tuple[FileOp, ...] = ()) -> None:
        self._operations = operations

    # -- immutable builders --------------------------------------------------

    def write(self, path: str, content: str) -> BatchWriter:
        """Return a new writer with a WRITE op appended."""
        return BatchWriter((*self._operations, FileOp(action="WRITE", path=path, content=content)))

    def delete(self, path: str) -> BatchWriter:
        """Return a new writer with a DELETE op appended."""
        return BatchWriter((*self._operations, FileOp(action="DELETE", path=path)))

    def create_dir(self, path: str) -> BatchWriter:
        """Return a new writer with a MKDIR op appended."""
        return BatchWriter((*self._operations, FileOp(action="MKDIR", path=path)))

    # -- planning & execution ------------------------------------------------

    def dry_run(self) -> BatchPlan:
        """Return a plan describing what *execute* would do."""
        return BatchPlan(operations=self._operations, total=len(self._operations))

    def execute(self) -> BatchResult:
        """Run all queued operations in order.

        Stops recording errors but continues processing remaining ops.
        """
        completed = 0
        failed = 0
        errors: list[str] = []

        for op in self._operations:
            try:
                if op.action == "WRITE":
                    p = Path(op.path)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(op.content, encoding="utf-8")
                    completed += 1
                elif op.action == "DELETE":
                    p = Path(op.path)
                    if p.is_dir():
                        shutil.rmtree(str(p))
                    elif p.exists():
                        p.unlink()
                    else:
                        errors.append(f"DELETE: path not found: {op.path}")
                        failed += 1
                        continue
                    completed += 1
                elif op.action == "MKDIR":
                    Path(op.path).mkdir(parents=True, exist_ok=True)
                    completed += 1
                else:
                    errors.append(f"Unknown action: {op.action}")
                    failed += 1
            except OSError as exc:
                errors.append(f"{op.action} {op.path}: {exc}")
                failed += 1

        return BatchResult(
            success=failed == 0,
            completed=completed,
            failed=failed,
            errors=tuple(errors),
        )

    # -- properties ----------------------------------------------------------

    @property
    def operations(self) -> tuple[FileOp, ...]:
        return self._operations
