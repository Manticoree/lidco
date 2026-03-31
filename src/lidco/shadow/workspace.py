"""Shadow workspace -- accumulates file edits without touching disk until approved."""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PendingWrite:
    """A staged file write that has not yet been applied to disk."""

    path: str
    new_content: str
    original_content: str | None  # None = new file


@dataclass
class ShadowApplyResult:
    """Result of applying pending changes to disk."""

    applied: list[str]
    skipped: list[str]
    errors: dict[str, str]


class ShadowWorkspace:
    """Intercepts file writes and accumulates them as pending changes.

    No files are touched until ``apply()`` is called.
    """

    def __init__(self) -> None:
        self._pending: dict[str, PendingWrite] = {}
        self._active: bool = False

    # -- activation --------------------------------------------------------

    @property
    def active(self) -> bool:
        """Whether the shadow workspace is currently intercepting writes."""
        return self._active

    def enable(self) -> None:
        """Start intercepting file writes."""
        self._active = True

    def disable(self) -> None:
        """Stop intercepting file writes (pending changes are kept)."""
        self._active = False

    # -- intercept ---------------------------------------------------------

    def intercept(self, path: str, new_content: str) -> None:
        """Store a pending file write without touching disk."""
        p = Path(path)
        original: str | None = None
        if p.exists():
            try:
                original = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                original = None
        self._pending[path] = PendingWrite(
            path=path,
            new_content=new_content,
            original_content=original,
        )

    def pending_paths(self) -> list[str]:
        """Return list of paths with pending changes."""
        return list(self._pending.keys())

    # -- diff --------------------------------------------------------------

    def get_diff(self, path: str | None = None) -> str:
        """Return unified diff for one file or all pending files."""
        targets = [path] if path else list(self._pending.keys())
        chunks: list[str] = []
        for p in targets:
            pw = self._pending.get(p)
            if pw is None:
                continue
            old_lines = (pw.original_content or "").splitlines(keepends=True)
            new_lines = pw.new_content.splitlines(keepends=True)
            diff = difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=f"a/{p}",
                tofile=f"b/{p}",
            )
            chunks.append("".join(diff))
        return "\n".join(chunks)

    # -- apply / discard ---------------------------------------------------

    def apply(self, paths: list[str] | None = None) -> ShadowApplyResult:
        """Write accepted changes to disk.

        Args:
            paths: Specific paths to apply.  ``None`` means apply all.

        Returns:
            An :class:`ShadowApplyResult` with lists of applied, skipped and errored paths.
        """
        targets = paths if paths is not None else list(self._pending.keys())
        applied: list[str] = []
        skipped: list[str] = []
        errors: dict[str, str] = {}

        for p in targets:
            pw = self._pending.get(p)
            if pw is None:
                skipped.append(p)
                continue
            try:
                out = Path(pw.path)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(pw.new_content, encoding="utf-8")
                applied.append(p)
                del self._pending[p]
            except OSError as exc:
                errors[p] = str(exc)

        return ShadowApplyResult(applied=applied, skipped=skipped, errors=errors)

    def discard(self, paths: list[str] | None = None) -> int:
        """Clear pending changes.

        Args:
            paths: Specific paths to discard.  ``None`` means discard all.

        Returns:
            Number of entries discarded.
        """
        if paths is None:
            count = len(self._pending)
            self._pending.clear()
            return count

        count = 0
        for p in paths:
            if p in self._pending:
                del self._pending[p]
                count += 1
        return count

    # -- summary -----------------------------------------------------------

    def summary(self) -> str:
        """One-line human-readable summary of pending changes."""
        n = len(self._pending)
        if n == 0:
            return "No pending changes."
        names = ", ".join(Path(p).name for p in list(self._pending.keys())[:5])
        suffix = f" (+{n - 5} more)" if n > 5 else ""
        return f"{n} file(s) pending: {names}{suffix}"
