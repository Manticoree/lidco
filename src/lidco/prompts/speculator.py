"""Prompt speculation engine — task 1098.

Predicts the next query a user is likely to issue and determines whether
prefetching related context would be beneficial.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Speculation:
    """An immutable prediction of the user's next query."""

    predicted_query: str
    confidence: float
    prefetch_keys: tuple[str, ...]


class PromptSpeculator:
    """Predict upcoming prompts from session history.

    All mutating operations return a *new* ``PromptSpeculator`` instance.

    Usage::

        spec = PromptSpeculator()
        spec = spec.add_history("list all TODOs")
        prediction = spec.speculate()
    """

    _CONFIDENCE_THRESHOLD = 0.3

    def __init__(self, history: tuple[str, ...] = ()) -> None:
        self._history = history

    # -- properties ----------------------------------------------------------

    @property
    def history(self) -> tuple[str, ...]:
        return self._history

    # -- public API ----------------------------------------------------------

    def speculate(self) -> Speculation:
        """Return a :class:`Speculation` based on current history."""
        if not self._history:
            return Speculation(
                predicted_query="",
                confidence=0.0,
                prefetch_keys=(),
            )

        last = self._history[-1].lower()

        # Pattern: after listing, user often acts on an item
        if any(kw in last for kw in ("list", "show", "find", "search")):
            return Speculation(
                predicted_query=f"Act on result of: {self._history[-1]}",
                confidence=min(0.8, 0.3 + len(self._history) * 0.1),
                prefetch_keys=("results", "selection"),
            )

        # Pattern: after fixing, user often runs tests
        if any(kw in last for kw in ("fix", "patch", "resolve", "repair")):
            return Speculation(
                predicted_query="Run tests",
                confidence=min(0.9, 0.4 + len(self._history) * 0.1),
                prefetch_keys=("test_results", "coverage"),
            )

        # Pattern: after writing code, user reviews or tests
        if any(kw in last for kw in ("write", "create", "add", "implement")):
            return Speculation(
                predicted_query="Review or test the implementation",
                confidence=min(0.7, 0.3 + len(self._history) * 0.05),
                prefetch_keys=("diff", "test_results"),
            )

        # Generic: repeat similar intent
        return Speculation(
            predicted_query=f"Follow-up to: {self._history[-1]}",
            confidence=max(0.1, min(0.5, len(self._history) * 0.1)),
            prefetch_keys=("context",),
        )

    def add_history(self, prompt: str) -> PromptSpeculator:
        """Return a new speculator with *prompt* appended to history."""
        return PromptSpeculator(history=(*self._history, prompt))

    def should_prefetch(self) -> bool:
        """Return True when speculation confidence exceeds threshold."""
        return self.speculate().confidence >= self._CONFIDENCE_THRESHOLD
