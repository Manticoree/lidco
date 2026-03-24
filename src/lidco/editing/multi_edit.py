# src/lidco/editing/multi_edit.py
"""Atomic multi-file edit transactions with rollback support."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EditStep:
    path: str
    old_string: str
    new_string: str
    replace_all: bool = False


@dataclass
class TransactionResult:
    applied: int
    failed: int
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.failed == 0


class MultiEditTransaction:
    """Collect a set of file edits and apply them atomically.

    If any edit fails, rollback() restores all previously written files.
    """

    def __init__(self) -> None:
        self._steps: list[EditStep] = []
        self._applied_backups: dict[str, str | None] = {}  # path → original content (None = new file)

    def add_edit(
        self,
        path: str,
        old_string: str,
        new_string: str,
        *,
        replace_all: bool = False,
    ) -> None:
        """Queue an edit step."""
        self._steps.append(EditStep(path=path, old_string=old_string, new_string=new_string, replace_all=replace_all))

    def validate(self) -> list[str]:
        """Return a list of validation error strings without modifying files."""
        errors: list[str] = []
        for step in self._steps:
            p = Path(step.path)
            if not p.exists():
                errors.append(f"File not found: {step.path}")
                continue
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                errors.append(f"Cannot read {step.path}: {e}")
                continue
            count = content.count(step.old_string)
            if count == 0:
                errors.append(f"{step.path}: old_string not found: {step.old_string[:60]!r}")
            elif count > 1 and not step.replace_all:
                errors.append(f"{step.path}: old_string found {count} times — use replace_all=True")
        return errors

    def apply(self) -> TransactionResult:
        """Apply all queued edits. Stops and records errors on failure."""
        applied = 0
        failed = 0
        errors: list[str] = []
        self._applied_backups.clear()

        for step in self._steps:
            p = Path(step.path)
            try:
                content = p.read_text(encoding="utf-8", errors="replace") if p.exists() else None
                if content is None:
                    errors.append(f"File not found: {step.path}")
                    failed += 1
                    continue

                count = content.count(step.old_string)
                if count == 0:
                    errors.append(f"{step.path}: old_string not found")
                    failed += 1
                    continue
                if count > 1 and not step.replace_all:
                    errors.append(f"{step.path}: ambiguous match ({count} occurrences)")
                    failed += 1
                    continue

                new_content = content.replace(step.old_string, step.new_string) if step.replace_all else content.replace(step.old_string, step.new_string, 1)
                # Save backup before writing
                self._applied_backups[step.path] = content
                p.write_text(new_content, encoding="utf-8")
                applied += 1
            except OSError as e:
                errors.append(f"{step.path}: {e}")
                failed += 1

        return TransactionResult(applied=applied, failed=failed, errors=errors)

    def rollback(self) -> None:
        """Restore all files that were modified during the last apply()."""
        for path_str, original in self._applied_backups.items():
            p = Path(path_str)
            try:
                if original is None:
                    p.unlink(missing_ok=True)
                else:
                    p.write_text(original, encoding="utf-8")
            except OSError:
                pass
        self._applied_backups.clear()

    @property
    def step_count(self) -> int:
        return len(self._steps)
