"""Proactive Hint Engine — generates contextual suggestions."""
from __future__ import annotations

from dataclasses import dataclass

from lidco.flow.action_tracker import ActionTracker
from lidco.flow.intent_inferrer import IntentInferrer


@dataclass
class Hint:
    """A proactive hint for the developer."""

    text: str
    category: str
    priority: int  # 1 (highest) to 5 (lowest)
    action_suggestion: str | None = None


# Hint templates keyed by intent.
_INTENT_HINTS: dict[str, list[tuple[str, str, int, str | None]]] = {
    "debugging": [
        ("Consider adding a breakpoint to isolate the issue", "debugging", 2, "Add breakpoint"),
        ("Run tests to isolate the failing code path", "debugging", 1, "Run pytest"),
        ("Check recent git changes for regression source", "debugging", 3, "Run git log"),
    ],
    "refactoring": [
        ("Run tests before committing refactored code", "refactoring", 1, "Run pytest"),
        ("Consider extracting repeated logic into a helper function", "refactoring", 2, None),
        ("Check for unused imports after refactoring", "refactoring", 3, None),
    ],
    "feature_dev": [
        ("Write tests first (TDD) for new functionality", "feature_dev", 1, "Create test file"),
        ("Update documentation for new features", "feature_dev", 3, None),
        ("Consider edge cases and error handling", "feature_dev", 2, None),
    ],
    "reviewing": [
        ("Look for missing error handling", "reviewing", 2, None),
        ("Check test coverage for reviewed code", "reviewing", 3, "Run coverage"),
    ],
    "exploring": [
        ("Use /search to find relevant code quickly", "exploring", 3, "/search"),
        ("Consider bookmarking important locations", "exploring", 4, None),
    ],
    "testing": [
        ("Aim for 80%+ test coverage", "testing", 2, "Run coverage"),
        ("Check edge cases and error paths", "testing", 2, None),
        ("Mock external dependencies properly", "testing", 3, None),
    ],
}


class HintEngine:
    """Generates proactive hints based on current flow state."""

    def __init__(self, tracker: ActionTracker, inferrer: IntentInferrer) -> None:
        self._tracker = tracker
        self._inferrer = inferrer
        self._dismissed: set[str] = set()

    def generate_hints(self, max_hints: int = 3) -> list[Hint]:
        """Generate up to *max_hints* contextual hints."""
        result: list[Hint] = []

        # High error rate hint (always check)
        error_rate = self._tracker.error_rate(window=50)
        if error_rate > 0.4:
            pct = int(error_rate * 100)
            text = f"Take a step back \u2014 {pct}% of recent actions failed"
            if text not in self._dismissed:
                result.append(Hint(
                    text=text,
                    category="error_rate",
                    priority=1,
                    action_suggestion="Review error patterns",
                ))

        # Intent-based hints
        inferred = self._inferrer.infer()
        templates = _INTENT_HINTS.get(inferred.intent, [])
        for text, category, priority, suggestion in templates:
            if text in self._dismissed:
                continue
            result.append(Hint(
                text=text,
                category=category,
                priority=priority,
                action_suggestion=suggestion,
            ))
            if len(result) >= max_hints:
                break

        # Sort by priority (lower number = higher priority)
        result.sort(key=lambda h: h.priority)
        return result[:max_hints]

    def dismiss(self, hint_text: str) -> None:
        """Dismiss a hint so it won't be shown again."""
        self._dismissed.add(hint_text)
