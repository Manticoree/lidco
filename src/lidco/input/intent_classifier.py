"""Intent classification for user prompts using regex and keyword matching."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class IntentType(Enum):
    """Supported intent types."""

    EDIT = "edit"
    ASK = "ask"
    DEBUG = "debug"
    GENERATE = "generate"
    REFACTOR = "refactor"
    EXPLAIN = "explain"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class IntentResult:
    """Result of intent classification."""

    intent: IntentType
    confidence: float
    suggested_command: Optional[str] = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            object.__setattr__(self, "confidence", max(0.0, min(1.0, self.confidence)))


# Patterns: list of (compiled regex, weight) per intent
_INTENT_PATTERNS: dict[IntentType, list[tuple[re.Pattern[str], float]]] = {
    IntentType.EDIT: [
        (re.compile(r"\b(fix|change|update|modify|replace|rename|move|delete|remove|add|insert|set|patch)\b", re.I), 0.8),
        (re.compile(r"\b(edit|rewrite|alter|adjust)\b", re.I), 0.85),
        (re.compile(r"\bfix\s+(the\s+)?bug\b", re.I), 0.9),
        (re.compile(r"\bchange\s+.+\s+to\b", re.I), 0.85),
    ],
    IntentType.ASK: [
        (re.compile(r"^(what|where|when|who|which|how|is|are|does|do|can|should|will|would|could)\b", re.I), 0.8),
        (re.compile(r"\?$"), 0.7),
        (re.compile(r"\b(tell me|show me|list|find|search|look up|what is|what are)\b", re.I), 0.75),
    ],
    IntentType.DEBUG: [
        (re.compile(r"\b(debug|trace|breakpoint|stack\s*trace|error|exception|crash|fail|broken|not working)\b", re.I), 0.8),
        (re.compile(r"\b(traceback|segfault|undefined|null\s*pointer|panic)\b", re.I), 0.85),
        (re.compile(r"\bwhy\s+(is|does|did)\s+.+\s+(fail|crash|error|break)\b", re.I), 0.9),
        (re.compile(r"\bfix\s+(the\s+)?(error|bug|crash|exception|issue)\b", re.I), 0.85),
    ],
    IntentType.GENERATE: [
        (re.compile(r"\b(generate|create|scaffold|write|build|make|new|implement|boilerplate)\b", re.I), 0.8),
        (re.compile(r"\b(write\s+a|create\s+a|generate\s+a|make\s+a|build\s+a)\b", re.I), 0.9),
        (re.compile(r"\b(from\s+scratch|skeleton|template|starter)\b", re.I), 0.75),
    ],
    IntentType.REFACTOR: [
        (re.compile(r"\b(refactor|restructure|reorganize|simplify|clean\s*up|optimize|extract|inline|decompose)\b", re.I), 0.9),
        (re.compile(r"\b(split|merge|decouple|consolidate|modularize)\b", re.I), 0.8),
        (re.compile(r"\b(dry|solid|kiss|yagni)\b", re.I), 0.7),
        (re.compile(r"\breduce\s+(complexity|duplication)\b", re.I), 0.85),
    ],
    IntentType.EXPLAIN: [
        (re.compile(r"\b(explain|describe|walk\s+me\s+through|how\s+does|what\s+does|understand)\b", re.I), 0.85),
        (re.compile(r"\b(documentation|docstring|comment|annotate)\b", re.I), 0.7),
        (re.compile(r"\b(break\s+down|step\s+by\s+step|in\s+detail)\b", re.I), 0.8),
        (re.compile(r"\bwhat\s+(is|are)\s+(this|that|these|those)\b", re.I), 0.75),
    ],
}

_COMMAND_MAP: dict[IntentType, str] = {
    IntentType.EDIT: "/edit",
    IntentType.ASK: "/ask",
    IntentType.DEBUG: "/debug",
    IntentType.GENERATE: "/generate",
    IntentType.REFACTOR: "/refactor",
    IntentType.EXPLAIN: "/explain",
}


class IntentClassifier:
    """Classifies user prompt intent using regex and keyword matching."""

    def __init__(self) -> None:
        self._patterns = _INTENT_PATTERNS
        self._command_map = _COMMAND_MAP

    def classify(self, prompt: str) -> IntentResult:
        """Classify the intent of a user prompt.

        Args:
            prompt: The user's input text.

        Returns:
            IntentResult with the detected intent, confidence, and optional command.
        """
        if not prompt or not prompt.strip():
            return IntentResult(
                intent=IntentType.UNKNOWN,
                confidence=0.0,
                suggested_command=None,
            )

        text = prompt.strip()
        scores: dict[IntentType, float] = {}

        for intent_type, patterns in self._patterns.items():
            max_score = 0.0
            for pattern, weight in patterns:
                if pattern.search(text):
                    max_score = max(max_score, weight)
            if max_score > 0:
                scores[intent_type] = max_score

        if not scores:
            return IntentResult(
                intent=IntentType.UNKNOWN,
                confidence=0.0,
                suggested_command=None,
            )

        # Pick the highest-scoring intent
        best_intent = max(scores, key=lambda k: scores[k])
        best_score = scores[best_intent]

        return IntentResult(
            intent=best_intent,
            confidence=round(best_score, 2),
            suggested_command=self._command_map.get(best_intent),
        )

    def classify_all(self, prompt: str) -> list[IntentResult]:
        """Return all matching intents sorted by confidence (descending)."""
        if not prompt or not prompt.strip():
            return []

        text = prompt.strip()
        results: list[IntentResult] = []

        for intent_type, patterns in self._patterns.items():
            max_score = 0.0
            for pattern, weight in patterns:
                if pattern.search(text):
                    max_score = max(max_score, weight)
            if max_score > 0:
                results.append(IntentResult(
                    intent=intent_type,
                    confidence=round(max_score, 2),
                    suggested_command=self._command_map.get(intent_type),
                ))

        results.sort(key=lambda r: r.confidence, reverse=True)
        return results
