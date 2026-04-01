"""Multi-edit engine — apply multiple text replacements to a single file atomically."""

from __future__ import annotations

import difflib
from dataclasses import dataclass


@dataclass(frozen=True)
class EditOp:
    """A single text replacement operation."""

    old_text: str
    new_text: str


@dataclass(frozen=True)
class EditConflict:
    """Describes a conflict found during validation."""

    index: int
    message: str


@dataclass(frozen=True)
class EditResult:
    """Outcome of applying edits."""

    success: bool
    content: str
    edits_applied: int
    conflicts: tuple[EditConflict, ...]


class MultiEditEngine:
    """Apply multiple ordered text replacements to file content.

    Immutable — ``add_edit`` returns a new instance.
    """

    def __init__(self, file_path: str, content: str) -> None:
        self._file_path = file_path
        self._content = content
        self._edits: tuple[EditOp, ...] = ()

    # -- immutable builder ---------------------------------------------------

    def add_edit(self, old_text: str, new_text: str) -> MultiEditEngine:
        """Return a *new* engine with the edit appended."""
        engine = MultiEditEngine(self._file_path, self._content)
        engine._edits = (*self._edits, EditOp(old_text=old_text, new_text=new_text))
        return engine

    # -- validation ----------------------------------------------------------

    def validate(self) -> tuple[EditConflict, ...]:
        """Check every edit can be applied without conflicts.

        Returns an empty tuple when all edits are valid.
        """
        conflicts: list[EditConflict] = []
        working = self._content
        for idx, edit in enumerate(self._edits):
            count = working.count(edit.old_text)
            if count == 0:
                conflicts.append(
                    EditConflict(index=idx, message=f"old_text not found: {edit.old_text[:60]!r}")
                )
            elif count > 1:
                conflicts.append(
                    EditConflict(
                        index=idx,
                        message=f"old_text is ambiguous ({count} occurrences): {edit.old_text[:60]!r}",
                    )
                )
            else:
                working = working.replace(edit.old_text, edit.new_text, 1)
        return tuple(conflicts)

    # -- apply ---------------------------------------------------------------

    def apply(self) -> EditResult:
        """Apply all edits sequentially, returning an :class:`EditResult`.

        Stops at the first conflict; already-applied edits are reflected in *content*.
        """
        conflicts = self.validate()
        if conflicts:
            return EditResult(
                success=False,
                content=self._content,
                edits_applied=0,
                conflicts=conflicts,
            )

        working = self._content
        applied = 0
        for edit in self._edits:
            if edit.old_text in working:
                working = working.replace(edit.old_text, edit.new_text, 1)
                applied += 1
        return EditResult(
            success=True,
            content=working,
            edits_applied=applied,
            conflicts=(),
        )

    # -- preview -------------------------------------------------------------

    def preview(self) -> str:
        """Return a unified diff between original and edited content."""
        result = self.apply()
        diff_lines = difflib.unified_diff(
            self._content.splitlines(),
            result.content.splitlines(),
            fromfile=self._file_path,
            tofile=f"{self._file_path} (edited)",
            lineterm="",
        )
        return "\n".join(diff_lines)

    # -- properties ----------------------------------------------------------

    @property
    def file_path(self) -> str:
        return self._file_path

    @property
    def content(self) -> str:
        return self._content

    @property
    def edits(self) -> tuple[EditOp, ...]:
        return self._edits
