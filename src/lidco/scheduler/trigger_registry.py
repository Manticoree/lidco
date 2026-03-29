"""AutomationTriggerRegistry — register and match automation triggers."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class AutomationTrigger:
    name: str
    trigger_type: str          # "cron", "github_pr", "slack", "linear", "webhook"
    config: dict               # type-specific config
    instructions_template: str  # template with {{title}}, {{body}}, {{source_id}} vars
    output_type: str           # "pr", "slack", "linear", "log", "comment"
    memory_key: str = ""       # key for cross-run memory
    enabled: bool = True


class TriggerAlreadyExistsError(Exception):
    pass


class AutomationTriggerRegistry:
    """Registry for automation triggers."""

    def __init__(self) -> None:
        self._triggers: dict[str, AutomationTrigger] = {}

    def register(self, trigger: AutomationTrigger, overwrite: bool = False) -> None:
        """Register a trigger. Raises TriggerAlreadyExistsError if name exists and overwrite=False."""
        if trigger.name in self._triggers and not overwrite:
            raise TriggerAlreadyExistsError(f"Trigger '{trigger.name}' already exists")
        self._triggers = {**self._triggers, trigger.name: trigger}

    def get(self, name: str) -> Optional[AutomationTrigger]:
        """Get a trigger by name."""
        return self._triggers.get(name)

    def match(self, event_type: str, payload: dict | None = None) -> list[AutomationTrigger]:
        """Return all enabled triggers with matching trigger_type."""
        return [
            t for t in self._triggers.values()
            if t.enabled and t.trigger_type == event_type
        ]

    def list_all(self) -> list[AutomationTrigger]:
        """Return all registered triggers."""
        return list(self._triggers.values())

    def disable(self, name: str) -> None:
        """Disable a trigger by name."""
        trigger = self._triggers.get(name)
        if trigger is not None:
            updated = AutomationTrigger(
                name=trigger.name,
                trigger_type=trigger.trigger_type,
                config=trigger.config,
                instructions_template=trigger.instructions_template,
                output_type=trigger.output_type,
                memory_key=trigger.memory_key,
                enabled=False,
            )
            self._triggers = {**self._triggers, name: updated}

    def enable(self, name: str) -> None:
        """Enable a trigger by name."""
        trigger = self._triggers.get(name)
        if trigger is not None:
            updated = AutomationTrigger(
                name=trigger.name,
                trigger_type=trigger.trigger_type,
                config=trigger.config,
                instructions_template=trigger.instructions_template,
                output_type=trigger.output_type,
                memory_key=trigger.memory_key,
                enabled=True,
            )
            self._triggers = {**self._triggers, name: updated}

    def to_json(self) -> str:
        """Serialize all triggers to JSON string."""
        triggers_data = [asdict(t) for t in self._triggers.values()]
        return json.dumps({"triggers": triggers_data}, indent=2)

    def from_json(self, data: str) -> None:
        """Load/merge triggers from a JSON string."""
        parsed = json.loads(data)
        for entry in parsed.get("triggers", []):
            trigger = AutomationTrigger(
                name=entry["name"],
                trigger_type=entry.get("trigger_type", "webhook"),
                config=entry.get("config", {}),
                instructions_template=entry.get("instructions_template", ""),
                output_type=entry.get("output_type", "log"),
                memory_key=entry.get("memory_key", ""),
                enabled=entry.get("enabled", True),
            )
            # Merge: overwrite existing
            self._triggers = {**self._triggers, trigger.name: trigger}
