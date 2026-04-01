"""Session state synchronization — Q189, task 1059."""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any


class SyncOpKind(enum.Enum):
    """Kind of synchronization operation."""

    ADD = "add"
    REMOVE = "remove"
    UPDATE = "update"


@dataclass(frozen=True)
class SyncOp:
    """Immutable description of a single sync operation."""

    kind: SyncOpKind
    key: str
    value: Any = None


@dataclass(frozen=True)
class SyncResult:
    """Immutable result of a state synchronization."""

    merged: dict[str, Any]
    conflicts: tuple[str, ...]


class SessionSync:
    """Synchronizes session state between local and remote endpoints."""

    def __init__(self, session_id: str) -> None:
        self._session_id = session_id

    @property
    def session_id(self) -> str:
        return self._session_id

    def sync_state(
        self, local: dict[str, Any], remote: dict[str, Any]
    ) -> SyncResult:
        """Merge local and remote state dicts.

        Keys present in both with different values are recorded as conflicts
        and resolved using local-wins strategy by default.
        """
        conflicts: list[str] = []
        merged: dict[str, Any] = {}

        all_keys = set(local) | set(remote)
        for key in sorted(all_keys):
            in_local = key in local
            in_remote = key in remote
            if in_local and in_remote:
                if local[key] != remote[key]:
                    conflicts.append(key)
                    merged[key] = local[key]  # local wins
                else:
                    merged[key] = local[key]
            elif in_local:
                merged[key] = local[key]
            else:
                merged[key] = remote[key]

        return SyncResult(merged=merged, conflicts=tuple(conflicts))

    def resolve_conflict(
        self,
        local: Any,
        remote: Any,
        strategy: str = "local_wins",
    ) -> dict[str, Any]:
        """Resolve a conflict between two values using the given strategy.

        Supported strategies: 'local_wins', 'remote_wins', 'merge'.
        For dicts with 'merge' strategy, keys from both sides are combined
        (remote wins on overlap).
        """
        if strategy == "local_wins":
            return {"resolved": local}
        if strategy == "remote_wins":
            return {"resolved": remote}
        if strategy == "merge":
            if isinstance(local, dict) and isinstance(remote, dict):
                return {"resolved": {**local, **remote}}
            # Non-dict merge falls back to remote wins
            return {"resolved": remote}
        raise ValueError(f"Unknown strategy: {strategy}")

    def compute_diff(
        self, old: dict[str, Any], new: dict[str, Any]
    ) -> tuple[SyncOp, ...]:
        """Compute the sequence of operations to transform *old* into *new*."""
        ops: list[SyncOp] = []
        all_keys = sorted(set(old) | set(new))
        for key in all_keys:
            in_old = key in old
            in_new = key in new
            if in_old and not in_new:
                ops.append(SyncOp(kind=SyncOpKind.REMOVE, key=key))
            elif not in_old and in_new:
                ops.append(SyncOp(kind=SyncOpKind.ADD, key=key, value=new[key]))
            elif old[key] != new[key]:
                ops.append(SyncOp(kind=SyncOpKind.UPDATE, key=key, value=new[key]))
        return tuple(ops)
