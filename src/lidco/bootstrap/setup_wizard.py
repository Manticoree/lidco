"""First-run setup wizard (simulated)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SetupStep:
    """A single setup wizard step."""

    name: str
    description: str
    required: bool = True
    completed: bool = False


@dataclass
class SetupConfig:
    """Configuration built during setup."""

    api_key: str = ""
    model: str = "claude-sonnet-4-6"
    preferences: dict[str, Any] = field(default_factory=dict)


class SetupWizard:
    """Interactive first-run setup wizard (simulated)."""

    def __init__(self) -> None:
        self._steps: dict[str, SetupStep] = {}
        self._order: list[str] = []
        self._config: SetupConfig = SetupConfig()

    def add_step(self, step: SetupStep) -> None:
        """Register a setup step."""
        self._steps[step.name] = step
        if step.name not in self._order:
            self._order.append(step.name)

    def complete_step(self, name: str) -> SetupStep:
        """Mark a step as completed and return the updated step."""
        if name not in self._steps:
            raise KeyError(f"Setup step '{name}' not found.")
        old = self._steps[name]
        updated = SetupStep(
            name=old.name,
            description=old.description,
            required=old.required,
            completed=True,
        )
        self._steps[name] = updated
        return updated

    def skip_step(self, name: str) -> SetupStep:
        """Skip a step (marks as completed). Only optional steps can be skipped."""
        if name not in self._steps:
            raise KeyError(f"Setup step '{name}' not found.")
        old = self._steps[name]
        if old.required:
            raise ValueError(f"Cannot skip required step '{name}'.")
        updated = SetupStep(
            name=old.name,
            description=old.description,
            required=old.required,
            completed=True,
        )
        self._steps[name] = updated
        return updated

    def is_complete(self) -> bool:
        """Return True if all required steps are completed."""
        return all(
            s.completed
            for s in self._steps.values()
            if s.required
        )

    def pending_steps(self) -> list[SetupStep]:
        """Return steps not yet completed."""
        return [self._steps[n] for n in self._order if not self._steps[n].completed]

    def completed_steps(self) -> list[SetupStep]:
        """Return steps that are completed."""
        return [self._steps[n] for n in self._order if self._steps[n].completed]

    def get_config(self) -> SetupConfig:
        """Return the current setup configuration."""
        return self._config

    def set_api_key(self, key: str) -> None:
        """Set the API key."""
        self._config.api_key = key

    def set_model(self, model: str) -> None:
        """Set the model name."""
        self._config.model = model

    def test_connection(self) -> bool:
        """Simulated connection test. Always returns True."""
        return True

    def summary(self) -> str:
        """Return a human-readable summary of setup state."""
        total = len(self._steps)
        done = sum(1 for s in self._steps.values() if s.completed)
        pending = total - done
        lines = [f"Setup: {done}/{total} steps completed."]
        if pending:
            for s in self.pending_steps():
                req = " (required)" if s.required else " (optional)"
                lines.append(f"  Pending: {s.name}{req} — {s.description}")
        if self._config.api_key:
            lines.append(f"  API key: configured")
        lines.append(f"  Model: {self._config.model}")
        return "\n".join(lines)
