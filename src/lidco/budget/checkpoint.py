"""Save and restore budget state for session resume."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BudgetCheckpoint:
    """Immutable snapshot of session budget state."""

    session_id: str = ""
    timestamp: float = field(default_factory=time.time)
    tokens_used: int = 0
    context_limit: int = 128000
    turns: int = 0
    compactions: int = 0
    debt: int = 0
    model: str = ""


class BudgetCheckpointManager:
    """Manage budget checkpoints for session persistence."""

    def __init__(self) -> None:
        self._checkpoints: list[BudgetCheckpoint] = []

    def save(
        self,
        session_id: str,
        tokens_used: int,
        context_limit: int = 128000,
        turns: int = 0,
        compactions: int = 0,
        debt: int = 0,
        model: str = "",
    ) -> BudgetCheckpoint:
        """Create and store a checkpoint."""
        cp = BudgetCheckpoint(
            session_id=session_id,
            tokens_used=tokens_used,
            context_limit=context_limit,
            turns=turns,
            compactions=compactions,
            debt=debt,
            model=model,
        )
        self._checkpoints = [*self._checkpoints, cp]
        return cp

    def load(self, session_id: str) -> BudgetCheckpoint | None:
        """Return the latest checkpoint for *session_id*, or ``None``."""
        matches = [c for c in self._checkpoints if c.session_id == session_id]
        if not matches:
            return None
        return max(matches, key=lambda c: c.timestamp)

    def serialize(self, checkpoint: BudgetCheckpoint) -> str:
        """Serialize *checkpoint* to a JSON string."""
        return json.dumps({
            "session_id": checkpoint.session_id,
            "timestamp": checkpoint.timestamp,
            "tokens_used": checkpoint.tokens_used,
            "context_limit": checkpoint.context_limit,
            "turns": checkpoint.turns,
            "compactions": checkpoint.compactions,
            "debt": checkpoint.debt,
            "model": checkpoint.model,
        })

    def deserialize(self, data: str) -> BudgetCheckpoint:
        """Parse a JSON string into a :class:`BudgetCheckpoint`."""
        d = json.loads(data)
        return BudgetCheckpoint(
            session_id=d.get("session_id", ""),
            timestamp=d.get("timestamp", 0.0),
            tokens_used=d.get("tokens_used", 0),
            context_limit=d.get("context_limit", 128000),
            turns=d.get("turns", 0),
            compactions=d.get("compactions", 0),
            debt=d.get("debt", 0),
            model=d.get("model", ""),
        )

    def is_stale(self, checkpoint: BudgetCheckpoint, max_age: float = 86400.0) -> bool:
        """Return ``True`` if *checkpoint* is older than *max_age* seconds."""
        return (time.time() - checkpoint.timestamp) > max_age

    def get_all(self) -> list[BudgetCheckpoint]:
        """Return all stored checkpoints."""
        return list(self._checkpoints)

    def clear(self) -> None:
        """Remove all checkpoints."""
        self._checkpoints = []

    def summary(self) -> str:
        """Human-readable summary of stored checkpoints."""
        lines = [f"Checkpoints stored: {len(self._checkpoints)}"]
        for cp in self._checkpoints[-5:]:
            lines.append(f"  {cp.session_id}: {cp.tokens_used:,} tokens, turn {cp.turns}")
        return "\n".join(lines)
