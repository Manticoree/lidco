"""Autonomy mode management — autonomous / supervised / interactive."""
from __future__ import annotations

from enum import Enum


class AutonomyMode(str, Enum):
    AUTONOMOUS = "autonomous"    # never ask, threshold=0.0
    SUPERVISED = "supervised"    # ask when uncertain, threshold=0.7
    INTERACTIVE = "interactive"  # ask before all risky, threshold=0.9


_THRESHOLDS: dict[AutonomyMode, float] = {
    AutonomyMode.AUTONOMOUS: 0.0,
    AutonomyMode.SUPERVISED: 0.7,
    AutonomyMode.INTERACTIVE: 0.9,
}


class AutonomyController:
    """Manage the current autonomy mode and its confidence threshold."""

    def __init__(self, mode: AutonomyMode = AutonomyMode.SUPERVISED) -> None:
        self._mode = mode

    @property
    def mode(self) -> AutonomyMode:
        return self._mode

    @property
    def threshold(self) -> float:
        return _THRESHOLDS[self._mode]

    def set_mode(self, mode: AutonomyMode | str) -> None:
        if isinstance(mode, str):
            mode = AutonomyMode(mode.lower())
        self._mode = mode

    def should_ask(self, confidence: float) -> bool:
        return confidence < self.threshold

    def display_name(self) -> str:
        return self._mode.value.upper()
