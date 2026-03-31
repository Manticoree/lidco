"""Q140 — DidYouMean: fuzzy command suggestions via difflib."""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Optional


@dataclass
class Suggestion:
    """A single suggestion result."""

    original: str
    suggested: str
    score: float
    context: str


class DidYouMean:
    """Suggest similar known commands for a misspelled input."""

    def __init__(self, known_commands: list[str]) -> None:
        self._commands: list[str] = list(known_commands)

    def suggest(self, input_str: str, max_results: int = 3) -> list[Suggestion]:
        """Return fuzzy-matched suggestions sorted by score descending."""
        scored: list[Suggestion] = []
        clean = input_str.lstrip("/")
        for cmd in self._commands:
            cmd_clean = cmd.lstrip("/")
            score = difflib.SequenceMatcher(None, clean, cmd_clean).ratio()
            if score > 0.4:
                scored.append(
                    Suggestion(
                        original=input_str,
                        suggested=cmd,
                        score=score,
                        context="command",
                    )
                )
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:max_results]

    def format_suggestion(self, input_str: str) -> str:
        """Return a human-readable 'Did you mean' string."""
        suggestions = self.suggest(input_str, max_results=1)
        if not suggestions:
            return f"Unknown command: {input_str}"
        best = suggestions[0]
        return f"Did you mean: /{best.suggested.lstrip('/')}?"

    def add_command(self, name: str) -> None:
        if name not in self._commands:
            self._commands.append(name)

    def remove_command(self, name: str) -> None:
        self._commands = [c for c in self._commands if c != name]

    def closest(self, input_str: str) -> Optional[str]:
        """Return the single best match or None if nothing scores > 0.4."""
        suggestions = self.suggest(input_str, max_results=1)
        if not suggestions:
            return None
        return suggestions[0].suggested
