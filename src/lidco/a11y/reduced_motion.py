"""Disable animations; static progress; instant transitions."""
from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass
class MotionPreference:
    """Motion-related preferences."""

    animations: bool = True
    spinners: bool = True
    transitions: bool = True
    scroll_smooth: bool = True


_ALL_OFF = MotionPreference(
    animations=False, spinners=False, transitions=False, scroll_smooth=False
)
_ALL_ON = MotionPreference()


class ReducedMotion:
    """Reduced-motion accessibility controller."""

    def __init__(self, enabled: bool = False) -> None:
        self._enabled = enabled
        self._prefs = MotionPreference() if not enabled else replace(_ALL_OFF)

    # -- enable / disable -----------------------------------------------------

    def enable(self) -> MotionPreference:
        self._enabled = True
        self._prefs = replace(_ALL_OFF)
        return replace(self._prefs)

    def disable(self) -> MotionPreference:
        self._enabled = False
        self._prefs = replace(_ALL_ON)
        return replace(self._prefs)

    def is_enabled(self) -> bool:
        return self._enabled

    # -- preferences ----------------------------------------------------------

    def preferences(self) -> MotionPreference:
        return replace(self._prefs)

    def set_preference(self, key: str, value: bool) -> MotionPreference:
        if not hasattr(self._prefs, key):
            raise ValueError(f"Unknown preference {key!r}")
        self._prefs = replace(self._prefs, **{key: value})
        return replace(self._prefs)

    # -- helpers --------------------------------------------------------------

    def should_animate(self) -> bool:
        return not self._enabled

    def progress_style(self) -> str:
        return "static" if self._enabled else "animated"

    # -- summary --------------------------------------------------------------

    def summary(self) -> dict:
        return {
            "enabled": self._enabled,
            "animations": self._prefs.animations,
            "spinners": self._prefs.spinners,
            "transitions": self._prefs.transitions,
            "scroll_smooth": self._prefs.scroll_smooth,
        }
