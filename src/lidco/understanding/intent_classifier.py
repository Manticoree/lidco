"""Classify user query intent."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class IntentType(str, Enum):
    """Types of user intent."""

    FIND = "find"
    EXPLAIN = "explain"
    REFACTOR = "refactor"
    FIX = "fix"
    GENERATE = "generate"
    NAVIGATE = "navigate"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ClassifiedIntent:
    """Result of intent classification."""

    intent: IntentType
    confidence: float
    secondary_intent: IntentType | None = None
    raw_query: str = ""


class IntentClassifier:
    """Keyword-based intent classifier for user queries."""

    PATTERNS: dict[IntentType, set[str]] = {
        IntentType.FIND: {
            "find", "search", "where", "locate", "look", "grep", "which",
            "show", "list", "lookup",
        },
        IntentType.EXPLAIN: {
            "explain", "what", "how", "why", "describe", "understand",
            "meaning", "purpose", "clarify", "tell",
        },
        IntentType.REFACTOR: {
            "refactor", "rename", "extract", "move", "restructure",
            "simplify", "clean", "reorganize", "improve", "optimize",
        },
        IntentType.FIX: {
            "fix", "bug", "error", "broken", "wrong", "issue", "crash",
            "fail", "debug", "repair",
        },
        IntentType.GENERATE: {
            "generate", "create", "write", "add", "new", "scaffold",
            "template", "make", "build", "implement",
        },
        IntentType.NAVIGATE: {
            "navigate", "goto", "jump", "open", "go", "switch", "visit",
            "definition", "reference", "usage",
        },
    }

    def __init__(self) -> None:
        self._extra_patterns: dict[IntentType, list[str]] = {}

    def classify(self, query: str) -> ClassifiedIntent:
        """Classify *query* into an intent with confidence."""
        keywords = self._extract_keywords(query)
        if not keywords:
            return ClassifiedIntent(
                intent=IntentType.UNKNOWN,
                confidence=0.0,
                raw_query=query,
            )

        scores: dict[IntentType, int] = {}
        for intent, pattern_set in self.PATTERNS.items():
            merged = pattern_set | set(self._extra_patterns.get(intent, []))
            overlap = keywords & merged
            if overlap:
                scores[intent] = len(overlap)

        if not scores:
            return ClassifiedIntent(
                intent=IntentType.UNKNOWN,
                confidence=0.0,
                raw_query=query,
            )

        ranked = sorted(scores.items(), key=lambda t: t[1], reverse=True)
        best_intent, best_count = ranked[0]
        total_kw = len(keywords)
        confidence = min(best_count / max(total_kw, 1), 1.0)

        secondary: IntentType | None = None
        if len(ranked) > 1:
            secondary = ranked[1][0]

        return ClassifiedIntent(
            intent=best_intent,
            confidence=round(confidence, 4),
            secondary_intent=secondary,
            raw_query=query,
        )

    def _extract_keywords(self, query: str) -> set[str]:
        """Extract lowercase keywords from a query."""
        return {w.strip("?.,!:;") for w in query.lower().split() if len(w) > 1}

    def add_pattern(self, intent: IntentType, keywords: list[str]) -> None:
        """Add extra keyword patterns for *intent*."""
        existing = self._extra_patterns.get(intent, [])
        self._extra_patterns[intent] = existing + keywords

    def list_patterns(self) -> dict[str, list[str]]:
        """Return all patterns including extras."""
        result: dict[str, list[str]] = {}
        for intent, base in self.PATTERNS.items():
            merged = sorted(base | set(self._extra_patterns.get(intent, [])))
            result[intent.value] = merged
        return result
