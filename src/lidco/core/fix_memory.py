"""Fix memory — learns from successful bug fixes cross-session."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_CATEGORY = "debug_fixes"
_MAX_RESULTS = 3
_MIN_KEYWORD_MATCHES = 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def confidence_label(c: float) -> str:
    """Return a human-readable label for a confidence score.

    >>> confidence_label(0.8)
    'HIGH'
    >>> confidence_label(0.5)
    'MEDIUM'
    >>> confidence_label(0.2)
    'LOW'
    """
    if c >= 0.7:
        return "HIGH"
    if c >= 0.4:
        return "MEDIUM"
    return "LOW"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class FixPattern:
    """A single recorded bug-fix pattern."""

    error_type: str
    file_module: str         # e.g. "lidco.core.session" (no src/)
    function_hint: str       # e.g. "load_config"
    error_signature: str     # first 80 chars of the error message
    fix_description: str     # what was fixed (LLM-generated, 1-2 sentences)
    diff_summary: str        # e.g. "+3/-1 lines, what changed"
    confidence: float        # 0.0–1.0
    session_id: str          # UUID
    created_at: str          # ISO datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_type": self.error_type,
            "file_module": self.file_module,
            "function_hint": self.function_hint,
            "error_signature": self.error_signature,
            "fix_description": self.fix_description,
            "diff_summary": self.diff_summary,
            "confidence": self.confidence,
            "session_id": self.session_id,
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> FixPattern:
        return FixPattern(
            error_type=data["error_type"],
            file_module=data["file_module"],
            function_hint=data["function_hint"],
            error_signature=data.get("error_signature", ""),
            fix_description=data.get("fix_description", ""),
            diff_summary=data.get("diff_summary", ""),
            confidence=float(data.get("confidence", 0.0)),
            session_id=data.get("session_id", ""),
            created_at=data.get("created_at", ""),
        )


# ---------------------------------------------------------------------------
# FixMemory
# ---------------------------------------------------------------------------


class FixMemory:
    """Cross-session fix memory backed by a :class:`~lidco.core.memory.MemoryStore`.

    Records successful bug-fix patterns so that similar errors in future
    sessions can benefit from prior solutions.
    """

    def __init__(self, memory_store: Any) -> None:
        # memory_store is lidco.core.memory.MemoryStore
        self._store = memory_store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        error_type: str,
        file_module: str,
        function_hint: str,
        error_signature: str,
        fix_description: str,
        diff_summary: str,
        confidence: float,
        session_id: str,
    ) -> FixPattern:
        """Create a :class:`FixPattern` and persist it to the memory store.

        The storage key is ``"{error_type}:{file_module}:{function_hint}"``.
        The pattern is serialised as JSON in the ``content`` field so that
        :meth:`find_similar` can reconstruct it later.
        """
        pattern = FixPattern(
            error_type=error_type,
            file_module=file_module,
            function_hint=function_hint,
            error_signature=error_signature[:80],
            fix_description=fix_description,
            diff_summary=diff_summary,
            confidence=max(0.0, min(1.0, confidence)),
            session_id=session_id,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        key = f"{error_type}:{file_module}:{function_hint}"
        self._store.add(
            key=key,
            content=json.dumps(pattern.to_dict(), ensure_ascii=False),
            category=_CATEGORY,
        )
        logger.debug("FixMemory: recorded fix for key=%s", key)
        return pattern

    def find_similar(
        self,
        error_type: str,
        file_module: str,
        error_message: str,
    ) -> list[FixPattern]:
        """Return up to 3 :class:`FixPattern` instances relevant to the error.

        Matching strategy (results are merged, deduplicated, then sorted):

        1. **Exact match**: entries where both ``error_type`` and
           ``file_module`` match exactly.
        2. **Keyword match**: split *error_message* into words; entries whose
           ``error_signature`` shares at least 2 of those words are included.

        Results are sorted by confidence descending and capped at 3.
        """
        all_entries = self._store.list_all(category=_CATEGORY)
        seen_keys: set[str] = set()
        results: list[FixPattern] = []

        # Phase 1: exact match on error_type + file_module
        for entry in all_entries:
            pattern = self._parse_entry(entry)
            if pattern is None:
                continue
            if pattern.error_type == error_type and pattern.file_module == file_module:
                dedup_key = f"{pattern.error_type}:{pattern.file_module}:{pattern.function_hint}"
                if dedup_key not in seen_keys:
                    seen_keys.add(dedup_key)
                    results.append(pattern)

        # Phase 2: keyword search on error_message vs error_signature
        message_words = {
            w.lower()
            for w in error_message.split()
            if len(w) >= 3
        }
        if message_words:
            for entry in all_entries:
                pattern = self._parse_entry(entry)
                if pattern is None:
                    continue
                dedup_key = f"{pattern.error_type}:{pattern.file_module}:{pattern.function_hint}"
                if dedup_key in seen_keys:
                    continue
                sig_words = {
                    w.lower()
                    for w in pattern.error_signature.split()
                    if len(w) >= 3
                }
                if len(message_words & sig_words) >= _MIN_KEYWORD_MATCHES:
                    seen_keys.add(dedup_key)
                    results.append(pattern)

        # Sort by confidence descending, cap at 3
        results.sort(key=lambda p: p.confidence, reverse=True)
        return results[:_MAX_RESULTS]

    def build_context(
        self,
        error_type: str,
        file_module: str,
        error_message: str,
    ) -> str:
        """Return a Markdown section with past fixes, or ``""`` if none found.

        Format::

            ## Past Fixes for Similar Errors
            1. [HIGH confidence] lidco.core.session:load_config → AttributeError
               Fix: Changed x to y.
               Changes: +3/-1 lines, updated guard clause
        """
        matches = self.find_similar(error_type, file_module, error_message)
        if not matches:
            return ""

        lines = ["## Past Fixes for Similar Errors"]
        for i, pattern in enumerate(matches, start=1):
            label = confidence_label(pattern.confidence)
            lines.append(
                f"{i}. [{label} confidence] {pattern.file_module}:{pattern.function_hint}"
                f" → {pattern.error_type}"
            )
            lines.append(f"   Fix: {pattern.fix_description}")
            lines.append(f"   Changes: {pattern.diff_summary}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _parse_entry(self, entry: Any) -> FixPattern | None:
        """Deserialise a :class:`~lidco.core.memory.MemoryEntry` into a :class:`FixPattern`."""
        try:
            data = json.loads(entry.content)
            return FixPattern.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.debug("FixMemory: failed to parse entry %s: %s", entry.key, exc)
            return None
