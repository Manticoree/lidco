"""NextEditPredictor — predict the most likely next code edit location."""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class EditEvent:
    """Represents a single past edit."""
    file: str
    line: int
    old: str
    new: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class EditSuggestion:
    """A predicted next edit."""
    file: str
    line: int
    old: str
    new: str
    confidence: float = 1.0

    def display(self) -> str:
        return f"[Tab] Accept suggested edit: {self.file}:{self.line}"


class NextEditPredictor:
    """Predicts the most likely next edit after a change, using LLM with caching."""

    TIMEOUT = 5.0  # seconds

    def __init__(self, llm_fn: Callable[..., Any] | None = None) -> None:
        """
        Args:
            llm_fn: async callable(prompt: str, max_tokens: int, temperature: float) -> str
                    If None, predictions are disabled (returns None).
        """
        self._llm_fn = llm_fn
        self._cache: dict[str, EditSuggestion | None] = {}
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def toggle(self) -> bool:
        self._enabled = not self._enabled
        return self._enabled

    def _cache_key(self, recent_edits: list[EditEvent], context: str) -> str:
        data = json.dumps(
            [{"file": e.file, "line": e.line, "old": e.old, "new": e.new} for e in recent_edits[-3:]]
        ) + context[:200]
        return hashlib.md5(data.encode()).hexdigest()

    async def predict(
        self,
        recent_edits: list[EditEvent],
        context: str = "",
    ) -> EditSuggestion | None:
        """Return an EditSuggestion or None (if disabled, no LLM, or uncertain)."""
        if not self._enabled or self._llm_fn is None:
            return None

        cache_key = self._cache_key(recent_edits, context)
        if cache_key in self._cache:
            return self._cache[cache_key]

        prompt = _build_prompt(recent_edits, context)

        try:
            raw = await asyncio.wait_for(
                self._llm_fn(prompt, max_tokens=300, temperature=0.3),
                timeout=self.TIMEOUT,
            )
            suggestion = _parse_response(raw)
        except (asyncio.TimeoutError, Exception):
            suggestion = None

        self._cache[cache_key] = suggestion
        return suggestion

    def clear_cache(self) -> None:
        self._cache.clear()


def _build_prompt(recent_edits: list[EditEvent], context: str) -> str:
    edits_desc = "\n".join(
        f"- {e.file}:{e.line}: '{e.old}' → '{e.new}'"
        for e in recent_edits[-3:]
    )
    return (
        f"Recent code edits:\n{edits_desc}\n\n"
        f"Context:\n{context[:500]}\n\n"
        "Predict the most likely NEXT edit. Respond with valid JSON only:\n"
        '{"file": "<path>", "line": <int>, "old": "<text>", "new": "<text>"}'
    )


def _parse_response(raw: str) -> EditSuggestion | None:
    """Parse LLM JSON response into an EditSuggestion."""
    raw = raw.strip()
    # Find JSON object in response
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    try:
        data = json.loads(raw[start:end])
        return EditSuggestion(
            file=str(data["file"]),
            line=int(data["line"]),
            old=str(data["old"]),
            new=str(data["new"]),
        )
    except (KeyError, ValueError, json.JSONDecodeError):
        return None
