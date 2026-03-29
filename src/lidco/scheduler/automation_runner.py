"""AutomationRunner — execute matched triggers via an injected agent function."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

from lidco.scheduler.trigger_registry import AutomationTriggerRegistry
from lidco.scheduler.trigger_normalizer import TriggerEventNormalizer


@dataclass
class RunRecord:
    id: str
    trigger_name: str
    input: str       # rendered instruction
    output: str      # agent result
    success: bool
    timestamp: str
    error: str = ""


@dataclass
class RunSummary:
    triggered: int
    succeeded: int
    failed: int
    records: list[RunRecord]


class AutomationRunner:
    """Run automation triggers against incoming events."""

    def __init__(
        self,
        registry: AutomationTriggerRegistry,
        agent_fn: Optional[Callable[[str], str]] = None,
        memory_store: Optional[dict] = None,
    ) -> None:
        self._registry = registry
        self._agent_fn = agent_fn
        self._memory_store: dict = memory_store if memory_store is not None else {}
        self._normalizer = TriggerEventNormalizer()
        self._history: list[RunRecord] = []

    def run(self, event_type: str, payload: dict) -> RunSummary:
        """Match triggers, normalize, render, call agent_fn, record results."""
        triggers = self._registry.match(event_type, payload)
        records: list[RunRecord] = []
        succeeded = 0
        failed = 0

        for trigger in triggers:
            normalized = self._normalizer.normalize(trigger.trigger_type, payload)
            if normalized is None:
                continue

            instruction = self._normalizer.render_template(
                trigger.instructions_template, normalized
            )

            # Prepend memory if memory_key set
            if trigger.memory_key and trigger.memory_key in self._memory_store:
                prev = self._memory_store[trigger.memory_key]
                instruction = f"Previous context: {prev}\n\n{instruction}"

            # Call agent
            output = ""
            error = ""
            success = True
            if self._agent_fn is not None:
                try:
                    output = self._agent_fn(instruction)
                except Exception as exc:
                    output = ""
                    error = str(exc)
                    success = False
            else:
                output = "[no agent configured]"

            # Store memory
            if trigger.memory_key and success:
                self._memory_store[trigger.memory_key] = output

            record = RunRecord(
                id=uuid.uuid4().hex[:12],
                trigger_name=trigger.name,
                input=instruction,
                output=output,
                success=success,
                timestamp=datetime.now(timezone.utc).isoformat(),
                error=error,
            )
            records.append(record)
            if success:
                succeeded += 1
            else:
                failed += 1

        self._history = [*self._history, *records]

        return RunSummary(
            triggered=len(records),
            succeeded=succeeded,
            failed=failed,
            records=records,
        )

    def get_history(self, limit: int = 10) -> list[RunRecord]:
        """Return last N run records."""
        return list(self._history[-limit:])

    def clear_history(self) -> None:
        """Clear all run history."""
        self._history = []
