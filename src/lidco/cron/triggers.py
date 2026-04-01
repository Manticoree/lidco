"""Event-based trigger system with compound triggers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TriggerType(str, Enum):
    """Types of triggers."""

    FILE_CHANGE = "file_change"
    GIT_PUSH = "git_push"
    TIME = "time"
    MANUAL = "manual"
    COMPOUND = "compound"


@dataclass(frozen=True)
class Trigger:
    """A single trigger definition."""

    name: str
    trigger_type: TriggerType
    config: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


@dataclass(frozen=True)
class CompoundTrigger:
    """A trigger combining multiple triggers with AND/OR logic."""

    name: str
    operator: str  # "AND" or "OR"
    triggers: tuple[Trigger, ...] = ()
    enabled: bool = True


class TriggerRegistry:
    """Registry for managing triggers."""

    def __init__(self) -> None:
        self._triggers: dict[str, Trigger] = {}
        self._compounds: dict[str, CompoundTrigger] = {}

    def add(self, trigger: Trigger) -> None:
        """Register a trigger."""
        self._triggers[trigger.name] = trigger

    def remove(self, name: str) -> bool:
        """Remove a trigger by name. Returns True if found."""
        if name in self._triggers:
            del self._triggers[name]
            return True
        if name in self._compounds:
            del self._compounds[name]
            return True
        return False

    def get(self, name: str) -> Trigger | None:
        """Get a trigger by name."""
        return self._triggers.get(name)

    def list_triggers(self) -> list[Trigger]:
        """List all simple triggers."""
        return list(self._triggers.values())

    def evaluate(self, name: str, context: dict[str, Any]) -> bool:
        """Evaluate whether a trigger should fire given *context*."""
        trigger = self._triggers.get(name)
        if trigger is None or not trigger.enabled:
            return False
        return self._evaluate_single(trigger, context)

    def add_compound(self, compound: CompoundTrigger) -> None:
        """Register a compound trigger."""
        self._compounds[compound.name] = compound

    def evaluate_compound(self, name: str, context: dict[str, Any]) -> bool:
        """Evaluate a compound trigger."""
        compound = self._compounds.get(name)
        if compound is None or not compound.enabled:
            return False
        if not compound.triggers:
            return False
        results = [self._evaluate_single(t, context) for t in compound.triggers]
        if compound.operator == "AND":
            return all(results)
        if compound.operator == "OR":
            return any(results)
        return False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _evaluate_single(trigger: Trigger, context: dict[str, Any]) -> bool:
        """Evaluate a single trigger against context."""
        if not trigger.enabled:
            return False
        if trigger.trigger_type == TriggerType.FILE_CHANGE:
            pattern = trigger.config.get("pattern", "")
            changed = context.get("changed_files", [])
            if not pattern:
                return len(changed) > 0
            return any(pattern in f for f in changed)
        if trigger.trigger_type == TriggerType.GIT_PUSH:
            return context.get("event") == "push"
        if trigger.trigger_type == TriggerType.TIME:
            return context.get("time_match", False)
        if trigger.trigger_type == TriggerType.MANUAL:
            return context.get("manual", False)
        return False
