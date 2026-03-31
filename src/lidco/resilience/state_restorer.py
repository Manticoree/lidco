"""State restorer that replays incomplete journal entries."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from lidco.resilience.crash_journal import JournalEntry


@dataclass
class RestoreResult:
    """Result of a state restoration attempt."""

    restored_steps: int = 0
    skipped_steps: int = 0
    status: str = "ok"
    errors: list[str] = field(default_factory=list)


class StateRestorer:
    """Restores system state from journal entries after a crash.

    Skips already-completed entries and attempts to re-execute
    or clean up incomplete ones.
    """

    def __init__(self) -> None:
        self._restore_handlers: dict[str, object] = {}

    def register_handler(self, action: str, handler: object) -> None:
        """Register a restore handler for a specific action type."""
        self._restore_handlers[action] = handler

    def restore(
        self,
        journal_entries: List[JournalEntry],
        git_state: Optional[dict] = None,
    ) -> RestoreResult:
        """Restore state from journal entries.

        Args:
            journal_entries: List of journal entries to process.
            git_state: Optional git state dict for context.

        Returns:
            RestoreResult with counts and status.
        """
        result = RestoreResult()

        if not journal_entries:
            result.status = "nothing_to_restore"
            return result

        for entry in journal_entries:
            if entry.completed:
                result.skipped_steps += 1
                continue

            try:
                self._restore_entry(entry, git_state)
                result.restored_steps += 1
            except Exception as exc:
                result.errors.append(f"{entry.id}: {exc}")

        if result.errors:
            result.status = "partial" if result.restored_steps > 0 else "failed"
        elif result.restored_steps > 0:
            result.status = "restored"
        else:
            result.status = "all_skipped"

        return result

    def _restore_entry(
        self, entry: JournalEntry, git_state: Optional[dict]
    ) -> None:
        """Attempt to restore a single entry."""
        handler = self._restore_handlers.get(entry.action)
        if handler is not None and callable(handler):
            handler(entry, git_state)
        # If no handler registered, we still count it as restored
        # (the entry is acknowledged)
