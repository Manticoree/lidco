"""Conversation analyzer for suggesting hookify rules (Task 1049)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from lidco.hookify.rule import ActionType, EventType


@dataclass(frozen=True)
class PatternMatch:
    """A detected pattern in conversation history."""

    pattern: str
    frequency: int
    examples: tuple[str, ...]
    risk_level: str  # LOW, MEDIUM, HIGH


@dataclass(frozen=True)
class SuggestedRule:
    """A rule suggestion derived from conversation analysis."""

    name: str
    event_type: EventType
    pattern: str
    action: ActionType
    message: str
    confidence: float


_DANGEROUS_PATTERNS: tuple[tuple[str, str, str, EventType, ActionType], ...] = (
    (r"rm\s+-rf\s+", "rm_rf_guard", "HIGH", EventType.BASH, ActionType.BLOCK),
    (r"git\s+push\s+(-f|--force)", "force_push_guard", "HIGH", EventType.BASH, ActionType.BLOCK),
    (r"\.env\b", "env_access_guard", "MEDIUM", EventType.FILE, ActionType.WARN),
    (r"\b(eval|exec)\s*\(", "eval_exec_guard", "HIGH", EventType.BASH, ActionType.WARN),
)


class ConversationAnalyzer:
    """Analyze conversation history to suggest hookify rules."""

    def analyze(self, conversation_history: list[dict]) -> tuple[SuggestedRule, ...]:
        """Analyze conversation and return suggested rules."""
        messages = [
            entry.get("content", "")
            for entry in conversation_history
            if isinstance(entry.get("content"), str)
        ]
        patterns = self.detect_patterns(messages)
        return self.suggest_rules(patterns)

    def detect_patterns(self, messages: list[str]) -> tuple[PatternMatch, ...]:
        """Detect dangerous patterns across messages."""
        results: list[PatternMatch] = []
        for regex, _name, risk, _evt, _act in _DANGEROUS_PATTERNS:
            examples: list[str] = []
            for msg in messages:
                for m in re.finditer(regex, msg):
                    examples.append(m.group(0))
            if examples:
                results.append(
                    PatternMatch(
                        pattern=regex,
                        frequency=len(examples),
                        examples=tuple(examples[:5]),
                        risk_level=risk,
                    )
                )
        return tuple(results)

    def suggest_rules(self, patterns: tuple[PatternMatch, ...]) -> tuple[SuggestedRule, ...]:
        """Convert detected patterns into rule suggestions."""
        suggestions: list[SuggestedRule] = []
        risk_confidence = {"HIGH": 0.9, "MEDIUM": 0.7, "LOW": 0.5}
        for pm in patterns:
            # Find matching dangerous pattern entry
            for regex, name, risk, evt, act in _DANGEROUS_PATTERNS:
                if regex == pm.pattern:
                    confidence = risk_confidence.get(pm.risk_level, 0.5)
                    # Boost confidence with frequency
                    confidence = min(1.0, confidence + pm.frequency * 0.02)
                    suggestions.append(
                        SuggestedRule(
                            name=name,
                            event_type=evt,
                            pattern=regex,
                            action=act,
                            message=f"Detected {pm.risk_level} risk pattern: {pm.pattern}",
                            confidence=confidence,
                        )
                    )
                    break
        return tuple(suggestions)


__all__ = [
    "ConversationAnalyzer",
    "SuggestedRule",
    "PatternMatch",
]
