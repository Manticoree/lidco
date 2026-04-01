"""Fan-out stream events to multiple output targets."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class OutputTarget(str, Enum):
    """Supported output target types."""

    TERMINAL = "terminal"
    FILE = "file"
    WEBSOCKET = "websocket"
    CALLBACK = "callback"


@dataclass(frozen=True)
class TargetConfig:
    """Configuration for a single output target."""

    name: str
    target_type: OutputTarget
    destination: str = ""
    active: bool = True


class FanOutMultiplexer:
    """Fan-out stream events to multiple named targets."""

    def __init__(self) -> None:
        self._targets: dict[str, TargetConfig] = {}
        self._buffer: list[str] = []
        self._stats: dict[str, int] = {}

    def add_target(
        self,
        name: str,
        target_type: OutputTarget,
        destination: str = "",
    ) -> TargetConfig:
        """Register a new output target."""
        cfg = TargetConfig(
            name=name,
            target_type=target_type,
            destination=destination,
        )
        self._targets = {**self._targets, name: cfg}
        self._stats = {**self._stats, name: self._stats.get(name, 0)}
        return cfg

    def remove_target(self, name: str) -> bool:
        """Remove target by name.  Returns ``True`` if it existed."""
        if name not in self._targets:
            return False
        self._targets = {k: v for k, v in self._targets.items() if k != name}
        return True

    def send(self, event_data: str, target_name: str | None = None) -> int:
        """Send *event_data* to a specific target or all active targets.

        Returns the number of targets the event was delivered to.
        """
        self._buffer = [*self._buffer, event_data]
        count = 0
        if target_name is not None:
            cfg = self._targets.get(target_name)
            if cfg and cfg.active:
                self._stats = {
                    **self._stats,
                    target_name: self._stats.get(target_name, 0) + 1,
                }
                count = 1
            return count
        for name, cfg in self._targets.items():
            if cfg.active:
                self._stats = {
                    **self._stats,
                    name: self._stats.get(name, 0) + 1,
                }
                count += 1
        return count

    def get_buffer(self, limit: int = 100) -> list[str]:
        """Return up to *limit* most-recent buffered events."""
        return list(self._buffer[-limit:])

    def get_targets(self) -> list[TargetConfig]:
        """Return all registered targets."""
        return list(self._targets.values())

    def pause_target(self, name: str) -> bool:
        """Pause a target (set active=False).  Returns ``True`` on success."""
        cfg = self._targets.get(name)
        if cfg is None:
            return False
        self._targets = {
            **self._targets,
            name: TargetConfig(
                name=cfg.name,
                target_type=cfg.target_type,
                destination=cfg.destination,
                active=False,
            ),
        }
        return True

    def resume_target(self, name: str) -> bool:
        """Resume a paused target.  Returns ``True`` on success."""
        cfg = self._targets.get(name)
        if cfg is None:
            return False
        self._targets = {
            **self._targets,
            name: TargetConfig(
                name=cfg.name,
                target_type=cfg.target_type,
                destination=cfg.destination,
                active=True,
            ),
        }
        return True

    def stats(self) -> dict[str, int]:
        """Return events-sent counts per target."""
        return dict(self._stats)

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [f"FanOutMultiplexer: {len(self._targets)} targets, {len(self._buffer)} buffered"]
        for name, cfg in self._targets.items():
            sent = self._stats.get(name, 0)
            state = "active" if cfg.active else "paused"
            lines.append(f"  {name} ({cfg.target_type.value}) [{state}] sent={sent}")
        return "\n".join(lines)
