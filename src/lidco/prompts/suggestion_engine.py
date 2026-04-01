"""Prompt suggestion engine — task 1097.

Analyzes prompt history and context to suggest likely next prompts.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Suggestion:
    """An immutable prompt suggestion."""

    text: str
    confidence: float
    source: str


class SuggestionEngine:
    """Generate prompt suggestions based on history and context.

    All mutating operations return a *new* ``SuggestionEngine`` instance.

    Usage::

        engine = SuggestionEngine()
        engine = engine.add_history("fix the login bug")
        engine = engine.add_context("Python FastAPI project")
        suggestions = engine.suggest(n=3)
    """

    def __init__(
        self,
        history: tuple[str, ...] = (),
        context: str = "",
    ) -> None:
        self._history = history
        self._context = context

    # -- properties ----------------------------------------------------------

    @property
    def history(self) -> tuple[str, ...]:
        return self._history

    @property
    def context(self) -> str:
        return self._context

    # -- public API ----------------------------------------------------------

    def suggest(self, n: int = 5) -> tuple[Suggestion, ...]:
        """Return up to *n* suggestions derived from history and context."""
        if n <= 0:
            return ()

        suggestions: list[Suggestion] = []

        # History-based suggestions (most recent first, higher confidence)
        for idx, prompt in enumerate(reversed(self._history)):
            if len(suggestions) >= n:
                break
            conf = max(0.1, 1.0 - idx * 0.15)
            suggestions.append(
                Suggestion(
                    text=f"Similar to: {prompt}",
                    confidence=round(conf, 2),
                    source="history",
                )
            )

        # Context-based suggestions
        if self._context and len(suggestions) < n:
            keywords = [w for w in self._context.split() if len(w) > 3]
            for kw in keywords[: n - len(suggestions)]:
                suggestions.append(
                    Suggestion(
                        text=f"Explore {kw}",
                        confidence=0.4,
                        source="context",
                    )
                )

        # Fallback generic suggestions
        generics = (
            "Explain this code",
            "Write tests",
            "Refactor for clarity",
            "Add error handling",
            "Improve performance",
        )
        for g in generics:
            if len(suggestions) >= n:
                break
            suggestions.append(
                Suggestion(text=g, confidence=0.2, source="generic")
            )

        return tuple(suggestions[:n])

    def add_context(self, context: str) -> SuggestionEngine:
        """Return a new engine with appended *context*."""
        merged = f"{self._context} {context}".strip() if self._context else context
        return SuggestionEngine(history=self._history, context=merged)

    def add_history(self, prompt: str) -> SuggestionEngine:
        """Return a new engine with *prompt* appended to history."""
        return SuggestionEngine(
            history=(*self._history, prompt),
            context=self._context,
        )
