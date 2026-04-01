"""Hookify rule definitions and types (Task 1047)."""
from __future__ import annotations

import enum
from dataclasses import dataclass


class EventType(enum.Enum):
    """Hook event types that rules can match against."""

    BASH = "bash"
    FILE = "file"
    STOP = "stop"
    PROMPT = "prompt"
    ALL = "all"


class ActionType(enum.Enum):
    """Action to take when a rule matches."""

    WARN = "warn"
    BLOCK = "block"


@dataclass(frozen=True)
class HookifyRule:
    """An immutable hook rule definition."""

    name: str
    event_type: EventType
    pattern: str
    action: ActionType
    message: str
    enabled: bool = True
    created_at: str = ""
    priority: int = 0


@dataclass(frozen=True)
class RuleMatch:
    """Result of a rule matching against content."""

    rule: HookifyRule
    matched_text: str
    event_type: EventType


__all__ = [
    "EventType",
    "ActionType",
    "HookifyRule",
    "RuleMatch",
]
