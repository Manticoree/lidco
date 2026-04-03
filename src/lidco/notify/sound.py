"""Sound engine — play sounds, mute, register custom events."""
from __future__ import annotations

import time
from dataclasses import dataclass


_DEFAULT_EVENTS = ["completion", "error", "warning", "notification"]


@dataclass(frozen=True)
class SoundEvent:
    """Record of a sound play event."""

    name: str
    sound_file: str | None = None
    timestamp: float = 0.0


class SoundEngine:
    """Play sounds with mute support and custom sound registration."""

    def __init__(self, muted: bool = False) -> None:
        self._muted = muted
        self._sounds: dict[str, str] = {}
        self._history: list[SoundEvent] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def play(self, event_name: str) -> SoundEvent:
        """Record a sound play event (actual playback is stubbed)."""
        file_path = self._sounds.get(event_name)
        event = SoundEvent(
            name=event_name,
            sound_file=file_path,
            timestamp=time.time(),
        )
        self._history.append(event)
        return event

    def register_sound(self, event_name: str, file_path: str) -> None:
        self._sounds[event_name] = file_path

    def mute(self) -> None:
        self._muted = True

    def unmute(self) -> None:
        self._muted = False

    def is_muted(self) -> bool:
        return self._muted

    def available_events(self) -> list[str]:
        all_events = list(_DEFAULT_EVENTS)
        for name in self._sounds:
            if name not in all_events:
                all_events.append(name)
        return all_events

    def history(self) -> list[SoundEvent]:
        return list(self._history)

    def summary(self) -> dict:
        return {
            "muted": self._muted,
            "registered": len(self._sounds),
            "played": len(self._history),
            "available_events": self.available_events(),
        }
