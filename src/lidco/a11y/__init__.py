"""Accessibility (a11y) package — screen reader, high contrast, reduced motion, voice control."""
from __future__ import annotations

from lidco.a11y.screen_reader import Annotation, Landmark, ScreenReaderSupport
from lidco.a11y.high_contrast import ContrastPair, HighContrastMode
from lidco.a11y.reduced_motion import MotionPreference, ReducedMotion
from lidco.a11y.voice_control import VoiceCommand, VoiceControl

__all__ = [
    "Annotation",
    "ContrastPair",
    "HighContrastMode",
    "Landmark",
    "MotionPreference",
    "ReducedMotion",
    "ScreenReaderSupport",
    "VoiceCommand",
    "VoiceControl",
]
