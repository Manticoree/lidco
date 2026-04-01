"""Edit planner — group and validate multi-file edit operations before execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileEdit:
    """A single text replacement within a file."""

    old_text: str
    new_text: str


@dataclass(frozen=True)
class EditGroup:
    """All edits targeting a single file."""

    path: str
    edits: tuple[FileEdit, ...]


@dataclass(frozen=True)
class EditPlan:
    """Validated plan ready for execution."""

    groups: tuple[EditGroup, ...]
    total_edits: int


class EditPlanner:
    """Immutable planner for multi-file edits.

    ``add_file_edit`` returns a new instance.
    """

    def __init__(self, file_edits: tuple[tuple[str, tuple[FileEdit, ...]], ...] = ()) -> None:
        self._file_edits = file_edits

    # -- immutable builder ---------------------------------------------------

    def add_file_edit(self, path: str, edits: tuple[FileEdit, ...]) -> EditPlanner:
        """Return a new planner with edits for *path* appended."""
        return EditPlanner((*self._file_edits, (path, edits)))

    # -- planning ------------------------------------------------------------

    def plan(self) -> EditPlan:
        """Build an :class:`EditPlan` grouping edits by file."""
        merged: dict[str, list[FileEdit]] = {}
        for path, edits in self._file_edits:
            merged.setdefault(path, []).extend(edits)

        groups: list[EditGroup] = []
        total = 0
        for path, edits_list in merged.items():
            group = EditGroup(path=path, edits=tuple(edits_list))
            groups.append(group)
            total += len(edits_list)

        return EditPlan(groups=tuple(groups), total_edits=total)

    # -- validation ----------------------------------------------------------

    def validate(self) -> tuple[str, ...]:
        """Return validation errors (empty tuple means valid)."""
        errors: list[str] = []
        for path, edits in self._file_edits:
            if not path:
                errors.append("Empty file path")
                continue
            p = Path(path)
            if not p.exists():
                errors.append(f"File not found: {path}")
                continue
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                errors.append(f"Cannot read {path}: {exc}")
                continue
            for edit in edits:
                count = content.count(edit.old_text)
                if count == 0:
                    errors.append(f"{path}: old_text not found: {edit.old_text[:60]!r}")
                elif count > 1:
                    errors.append(f"{path}: ambiguous old_text ({count} occurrences): {edit.old_text[:60]!r}")
        return tuple(errors)

    # -- properties ----------------------------------------------------------

    @property
    def file_edits(self) -> tuple[tuple[str, tuple[FileEdit, ...]], ...]:
        return self._file_edits
