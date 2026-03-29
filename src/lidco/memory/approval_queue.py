"""MemoryApprovalQueue -- pending fact approval/rejection with JSON persistence."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .conversation_extractor import ExtractedFact


@dataclass
class PendingFact:
    """A fact awaiting approval."""

    id: str
    fact: ExtractedFact
    created_at: str  # ISO timestamp

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "fact": self.fact.to_dict(),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PendingFact:
        return cls(
            id=d["id"],
            fact=ExtractedFact.from_dict(d["fact"]),
            created_at=d["created_at"],
        )


class FactNotFoundError(Exception):
    """Raised when a fact id is not found in the queue."""


class MemoryApprovalQueue:
    """Queue for facts awaiting human approval before committing to memory."""

    def __init__(self, storage_path: str = ".lidco/approval_queue.json") -> None:
        self._path = Path(storage_path)
        self._pending: dict[str, PendingFact] = {}
        self._load()

    def add(self, fact: ExtractedFact) -> str:
        """Add a fact to the pending queue. Returns the assigned id."""
        fact_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()
        pending = PendingFact(id=fact_id, fact=fact, created_at=now)
        self._pending[fact_id] = pending
        self._save()
        return fact_id

    def approve(self, fact_id: str) -> ExtractedFact:
        """Approve and remove a pending fact. Returns the fact."""
        if fact_id not in self._pending:
            raise FactNotFoundError(f"Fact not found: {fact_id}")
        pending = self._pending.pop(fact_id)
        self._save()
        return pending.fact

    def reject(self, fact_id: str) -> None:
        """Reject and remove a pending fact."""
        if fact_id not in self._pending:
            raise FactNotFoundError(f"Fact not found: {fact_id}")
        del self._pending[fact_id]
        self._save()

    def list_pending(self) -> list[PendingFact]:
        """Return all pending facts ordered by creation time."""
        items = sorted(self._pending.values(), key=lambda p: p.created_at)
        return list(items)

    def auto_approve(self, threshold: float = 0.9) -> list[ExtractedFact]:
        """Auto-approve facts with confidence >= threshold. Returns approved facts."""
        approved: list[ExtractedFact] = []
        to_remove: list[str] = []
        for fid, pending in self._pending.items():
            if pending.fact.confidence >= threshold:
                approved.append(pending.fact)
                to_remove.append(fid)
        for fid in to_remove:
            del self._pending[fid]
        if to_remove:
            self._save()
        return approved

    def count(self) -> int:
        """Return number of pending facts."""
        return len(self._pending)

    def get(self, fact_id: str) -> PendingFact | None:
        """Get a pending fact by id, or None."""
        return self._pending.get(fact_id)

    def clear(self) -> int:
        """Remove all pending facts. Returns count removed."""
        count = len(self._pending)
        self._pending.clear()
        self._save()
        return count

    def _load(self) -> None:
        """Load queue from JSON file."""
        if not self._path.exists():
            self._pending = {}
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
            self._pending = {}
            for item in data:
                pf = PendingFact.from_dict(item)
                self._pending[pf.id] = pf
        except (json.JSONDecodeError, KeyError, TypeError):
            self._pending = {}

    def _save(self) -> None:
        """Persist queue to JSON file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        items = [p.to_dict() for p in self._pending.values()]
        self._path.write_text(json.dumps(items, indent=2), encoding="utf-8")
