"""CommitAmender — safe amend / fixup helpers (no real git calls).

All methods work on *data* — no subprocess calls.  Real git interaction
is the caller's responsibility.
"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FixupEntry:
    """Represents a fixup commit referencing an original."""

    fixup_id: str
    original_hash: str
    message: str
    timestamp: float = 0.0


@dataclass(frozen=True)
class SquashPlanEntry:
    """One step in an auto-squash plan."""

    action: str  # "pick" | "fixup" | "squash"
    commit_hash: str
    message: str


# ---------------------------------------------------------------------------
# CommitAmender
# ---------------------------------------------------------------------------

class CommitAmender:
    """Safe amend / fixup utilities.

    Maintains an in-memory store of fixup entries and preserved originals
    so that callers can preview plans before executing real git commands.
    """

    def __init__(self) -> None:
        self._fixups: List[FixupEntry] = []
        self._preserved: Dict[str, str] = {}  # hash -> backup_ref
        self._amendable_hashes: set[str] = set()

    # -- public API -----------------------------------------------------

    def mark_amendable(self, commit_hash: str) -> None:
        """Mark *commit_hash* as safe to amend (e.g. it's the HEAD)."""
        self._amendable_hashes.add(commit_hash)

    def can_amend(self, commit_hash: str) -> bool:
        """Return *True* if *commit_hash* has been marked amendable."""
        return commit_hash in self._amendable_hashes

    def create_fixup(self, original_hash: str, message: str) -> str:
        """Create a fixup entry.  Returns the generated fixup id."""
        fixup_id = self._make_id(original_hash, message)
        entry = FixupEntry(
            fixup_id=fixup_id,
            original_hash=original_hash,
            message=f"fixup! {message}",
            timestamp=time.time(),
        )
        self._fixups = [*self._fixups, entry]
        return fixup_id

    def preserve_original(self, commit_hash: str) -> str:
        """Store a backup reference for *commit_hash*.  Returns the ref."""
        ref = f"refs/original/{commit_hash[:8]}"
        self._preserved = {**self._preserved, commit_hash: ref}
        return ref

    def get_preserved(self, commit_hash: str) -> Optional[str]:
        """Retrieve preserved ref for *commit_hash*, or *None*."""
        return self._preserved.get(commit_hash)

    def auto_squash_plan(
        self, commits: Sequence[str]
    ) -> List[SquashPlanEntry]:
        """Generate an auto-squash rebase plan.

        *commits* is an ordered list of commit hashes (oldest first).
        Fixup entries that reference a commit in *commits* are turned into
        ``fixup`` actions; everything else is ``pick``.
        """
        fixup_targets: dict[str, list[FixupEntry]] = {}
        for fe in self._fixups:
            fixup_targets.setdefault(fe.original_hash, []).append(fe)

        plan: list[SquashPlanEntry] = []
        for h in commits:
            plan.append(SquashPlanEntry(action="pick", commit_hash=h, message=h))
            for fe in fixup_targets.get(h, []):
                plan.append(
                    SquashPlanEntry(
                        action="fixup",
                        commit_hash=fe.fixup_id,
                        message=fe.message,
                    )
                )
        return plan

    @property
    def fixups(self) -> List[FixupEntry]:
        """Return a copy of the fixup list."""
        return list(self._fixups)

    # -- helpers --------------------------------------------------------

    @staticmethod
    def _make_id(original_hash: str, message: str) -> str:
        raw = f"{original_hash}:{message}:{time.monotonic_ns()}"
        return hashlib.sha1(raw.encode()).hexdigest()[:12]
