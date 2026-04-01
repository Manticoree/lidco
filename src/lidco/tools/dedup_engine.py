"""Detect and deduplicate tool calls."""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DedupRecord:
    """Record of a deduplicated tool call."""

    tool_name: str
    args: str
    call_count: int = 1
    first_seen: float = field(default_factory=time.time)
    last_result: str = ""


class DedupEngine:
    """Track tool calls and return cached results for duplicates."""

    def __init__(self) -> None:
        self._records: dict[str, DedupRecord] = {}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _key(tool_name: str, args: str) -> str:
        raw = f"{tool_name}:{args}"
        return hashlib.md5(raw.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, tool_name: str, args: str) -> str | None:
        """Return cached result if this call was seen before, else None."""
        key = self._key(tool_name, args)
        rec = self._records.get(key)
        if rec is None:
            return None
        # Bump call_count immutably
        updated = DedupRecord(
            tool_name=rec.tool_name,
            args=rec.args,
            call_count=rec.call_count + 1,
            first_seen=rec.first_seen,
            last_result=rec.last_result,
        )
        self._records[key] = updated
        return rec.last_result

    def record(self, tool_name: str, args: str, result: str) -> DedupRecord:
        """Store a tool call and its result."""
        key = self._key(tool_name, args)
        existing = self._records.get(key)
        rec = DedupRecord(
            tool_name=tool_name,
            args=args,
            call_count=(existing.call_count if existing else 0) + 1,
            first_seen=existing.first_seen if existing else time.time(),
            last_result=result,
        )
        self._records[key] = rec
        return rec

    def get_duplicates(self) -> list[DedupRecord]:
        """Return all records with call_count > 1."""
        return [r for r in self._records.values() if r.call_count > 1]

    def savings(self) -> dict:
        """Estimate dedup savings."""
        total_calls = sum(r.call_count for r in self._records.values())
        unique_calls = len(self._records)
        deduped = total_calls - unique_calls
        # Rough estimate: ~50 tokens saved per deduped call
        return {
            "total_calls": total_calls,
            "unique_calls": unique_calls,
            "deduped_calls": deduped,
            "saved_tokens": deduped * 50,
        }

    def clear(self) -> None:
        """Remove all records."""
        self._records = {}

    def summary(self) -> str:
        """Human-readable summary."""
        s = self.savings()
        return (
            f"DedupEngine: {s['unique_calls']} unique / {s['total_calls']} total calls, "
            f"{s['deduped_calls']} deduped (~{s['saved_tokens']} tokens saved)"
        )
