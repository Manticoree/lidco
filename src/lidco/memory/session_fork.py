"""SessionForkManager — create and manage session forks (branches).

Task 733: Q120.
"""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class SessionFork:
    fork_id: str
    parent_session_id: str
    title: str
    branch_point_turn: int
    turns: list[dict]
    created_at: str = ""


@dataclass
class ForkDiff:
    fork_a_id: str
    fork_b_id: str
    common_prefix_turns: int
    added: int    # turns in fork_b beyond prefix
    removed: int  # turns in fork_a beyond prefix


class SessionForkManager:
    """Create, store, and diff session forks."""

    def __init__(self) -> None:
        self._forks: dict[str, SessionFork] = {}

    def create(
        self,
        parent_session_id: str,
        title: str,
        parent_turns: list[dict],
        branch_point_turn: Optional[int] = None,
    ) -> SessionFork:
        """Create a fork from *parent_turns* up to *branch_point_turn*."""
        if branch_point_turn is None:
            branch_point_turn = len(parent_turns)

        turns = [copy.deepcopy(t) for t in parent_turns[:branch_point_turn]]
        fork = SessionFork(
            fork_id=uuid.uuid4().hex[:12],
            parent_session_id=parent_session_id,
            title=title,
            branch_point_turn=branch_point_turn,
            turns=turns,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._forks[fork.fork_id] = fork
        return fork

    def get(self, fork_id: str) -> Optional[SessionFork]:
        return self._forks.get(fork_id)

    def list_all(self) -> list[SessionFork]:
        return list(self._forks.values())

    def delete(self, fork_id: str) -> None:
        self._forks.pop(fork_id, None)

    def append_turn(self, fork_id: str, turn: dict) -> SessionFork:
        fork = self._forks.get(fork_id)
        if fork is None:
            raise KeyError(f"Fork not found: {fork_id!r}")
        fork.turns = [*fork.turns, turn]
        return fork

    def diff(self, fork_a_id: str, fork_b_id: str) -> ForkDiff:
        """Compute the diff between two forks."""
        fork_a = self._forks[fork_a_id]
        fork_b = self._forks[fork_b_id]

        # Common prefix length
        common = 0
        for ta, tb in zip(fork_a.turns, fork_b.turns):
            if ta == tb:
                common += 1
            else:
                break

        added = len(fork_b.turns) - common
        removed = len(fork_a.turns) - common

        return ForkDiff(
            fork_a_id=fork_a_id,
            fork_b_id=fork_b_id,
            common_prefix_turns=common,
            added=added,
            removed=removed,
        )
