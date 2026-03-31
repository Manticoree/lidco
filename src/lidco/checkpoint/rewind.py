"""Rewind engine for selective code/conversation restoration — Q160."""

from __future__ import annotations

import difflib
from typing import Callable

from lidco.checkpoint.manager import CheckpointManager, RewindResult


class RewindEngine:
    """High-level rewind operations on top of :class:`CheckpointManager`."""

    def __init__(self, manager: CheckpointManager) -> None:
        self._manager = manager

    # -- selective rewind ---------------------------------------------------

    def rewind_code(
        self,
        checkpoint_id: str,
        write_fn: Callable[[str, str], None],
    ) -> list[str]:
        """Restore files from *checkpoint_id* using *write_fn*.

        Returns the list of restored file paths.
        """
        cp = self._manager.get(checkpoint_id)
        if cp is None:
            return []
        restored: list[str] = []
        for path, content in cp.file_snapshots.items():
            write_fn(path, content)
            restored.append(path)
        return restored

    def rewind_chat(self, checkpoint_id: str) -> int:
        """Return the conversation position to truncate to.

        Returns ``-1`` if the checkpoint is not found.
        """
        cp = self._manager.get(checkpoint_id)
        if cp is None:
            return -1
        return cp.conversation_length

    def rewind_both(
        self,
        checkpoint_id: str,
        write_fn: Callable[[str, str], None],
    ) -> RewindResult:
        """Rewind both code and conversation position."""
        restored = self.rewind_code(checkpoint_id, write_fn)
        chat_pos = self.rewind_chat(checkpoint_id)
        if not restored and chat_pos == -1:
            return RewindResult(
                restored_files=[],
                conversation_truncate_to=None,
                success=False,
            )
        return RewindResult(
            restored_files=restored,
            conversation_truncate_to=chat_pos if chat_pos >= 0 else None,
            success=True,
        )

    # -- diff ---------------------------------------------------------------

    def diff_from_checkpoint(
        self,
        checkpoint_id: str,
        current_files: dict[str, str],
    ) -> dict[str, str]:
        """Show unified diffs between checkpoint and current file contents.

        Returns a mapping of ``path -> diff_text`` for files that differ.
        Files absent in the checkpoint are shown as fully added; files absent
        in *current_files* are shown as fully deleted.
        """
        cp = self._manager.get(checkpoint_id)
        if cp is None:
            return {}

        all_paths = set(cp.file_snapshots) | set(current_files)
        diffs: dict[str, str] = {}
        for path in sorted(all_paths):
            old = cp.file_snapshots.get(path, "")
            new = current_files.get(path, "")
            if old == new:
                continue
            diff_lines = difflib.unified_diff(
                old.splitlines(keepends=True),
                new.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
            diff_text = "".join(diff_lines)
            if diff_text:
                diffs[path] = diff_text
        return diffs
