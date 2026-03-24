"""REPL integration for next-edit prediction display."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable

from .next_edit import EditEvent, EditSuggestion, NextEditPredictor


@dataclass
class DisplayConfig:
    """Configuration for next-edit display."""
    enabled: bool = False
    timeout: float = 5.0
    dim_style: str = "dim"


class NextEditDisplay:
    """Manages next-edit prediction display in the REPL."""

    def __init__(self, predictor: NextEditPredictor, config: DisplayConfig | None = None) -> None:
        self._predictor = predictor
        self._config = config or DisplayConfig()
        self._pending: EditSuggestion | None = None

    @property
    def config(self) -> DisplayConfig:
        return self._config

    def enable(self) -> None:
        self._config.enabled = True
        self._predictor.enable()

    def disable(self) -> None:
        self._config.enabled = False
        self._predictor.disable()

    async def after_edit(self, recent_edits: list[EditEvent], context: str = "") -> EditSuggestion | None:
        """Call after an agent edit to get and store prediction."""
        if not self._config.enabled:
            return None
        try:
            suggestion = await asyncio.wait_for(
                self._predictor.predict(recent_edits, context),
                timeout=self._config.timeout,
            )
            self._pending = suggestion
            return suggestion
        except asyncio.TimeoutError:
            self._pending = None
            return None

    def format_suggestion(self, suggestion: EditSuggestion) -> str:
        """Format the suggestion for display."""
        return f"[Tab] Next edit: {suggestion.file}:{suggestion.line} — {suggestion.new[:40]}"

    def accept(self) -> EditSuggestion | None:
        """Accept the pending suggestion."""
        s = self._pending
        self._pending = None
        return s

    def dismiss(self) -> None:
        """Dismiss the pending suggestion."""
        self._pending = None

    @property
    def has_pending(self) -> bool:
        return self._pending is not None
