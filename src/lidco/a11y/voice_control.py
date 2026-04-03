"""Voice command recognition; dictation; navigation; wake word."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceCommand:
    """A registered voice command."""

    phrase: str
    action: str
    category: str = "navigation"


class VoiceControl:
    """Voice command registration and matching."""

    def __init__(self, wake_word: str = "hey lidco", enabled: bool = False) -> None:
        self._wake_word = wake_word
        self._enabled = enabled
        self._commands: dict[str, VoiceCommand] = {}

    # -- enable / disable -----------------------------------------------------

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def is_enabled(self) -> bool:
        return self._enabled

    # -- command management ---------------------------------------------------

    def register_command(
        self, phrase: str, action: str, category: str = "navigation"
    ) -> VoiceCommand:
        cmd = VoiceCommand(phrase=phrase, action=action, category=category)
        self._commands[phrase.lower()] = cmd
        return cmd

    def unregister_command(self, phrase: str) -> bool:
        return self._commands.pop(phrase.lower(), None) is not None

    # -- matching -------------------------------------------------------------

    def match(self, input_text: str) -> VoiceCommand | None:
        """Fuzzy match *input_text* against registered commands.

        Tries exact match first, then substring, then word-overlap scoring.
        """
        text = input_text.strip().lower()
        # Strip wake word prefix if present.
        ww = self._wake_word.lower()
        if text.startswith(ww):
            text = text[len(ww):].strip()
        if not text:
            return None

        # Exact match.
        if text in self._commands:
            return self._commands[text]

        # Substring match.
        for key, cmd in self._commands.items():
            if key in text or text in key:
                return cmd

        # Word-overlap scoring.
        input_words = set(re.findall(r"\w+", text))
        best: VoiceCommand | None = None
        best_score = 0
        for key, cmd in self._commands.items():
            cmd_words = set(re.findall(r"\w+", key))
            overlap = len(input_words & cmd_words)
            if overlap > best_score:
                best_score = overlap
                best = cmd
        return best if best_score > 0 else None

    # -- wake word ------------------------------------------------------------

    def set_wake_word(self, word: str) -> None:
        self._wake_word = word

    # -- queries --------------------------------------------------------------

    def commands(self, category: str | None = None) -> list[VoiceCommand]:
        cmds = list(self._commands.values())
        if category is not None:
            cmds = [c for c in cmds if c.category == category]
        return cmds

    def categories(self) -> list[str]:
        return sorted({c.category for c in self._commands.values()})

    # -- summary --------------------------------------------------------------

    def summary(self) -> dict:
        return {
            "enabled": self._enabled,
            "wake_word": self._wake_word,
            "commands": len(self._commands),
            "categories": self.categories(),
        }
