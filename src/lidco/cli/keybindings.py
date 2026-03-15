"""Keybinding customization for LIDCO REPL — Task 432."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_BINDINGS: dict[str, str] = {
    "submit": "enter",
    "newline": "escape enter",
    "clear": "c-l",
    "abort": "c-c",
    "history_up": "up",
    "history_down": "down",
    "open_editor": "escape e",
    "show_help": "f1",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class KeybindingConfig:
    """Resolved keybinding configuration.

    Attributes:
        bindings: Mapping from action name to key sequence string.
    """

    bindings: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_BINDINGS))

    def get(self, action: str) -> str | None:
        """Return the key sequence for *action*, or None if not bound."""
        return self.bindings.get(action)

    def set(self, action: str, key: str) -> "KeybindingConfig":
        """Return a new config with *action* bound to *key*."""
        return KeybindingConfig(bindings={**self.bindings, action: key})

    def reset(self) -> "KeybindingConfig":
        """Return a config reset to defaults."""
        return KeybindingConfig(bindings=dict(DEFAULT_BINDINGS))

    def list_actions(self) -> list[str]:
        """Sorted list of known action names."""
        return sorted(self.bindings)


# ---------------------------------------------------------------------------
# Loader / saver
# ---------------------------------------------------------------------------

class KeybindingLoader:
    """Loads and saves keybindings from/to ``~/.lidco/keybindings.json``."""

    DEFAULT_PATH = Path.home() / ".lidco" / "keybindings.json"

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or self.DEFAULT_PATH

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> KeybindingConfig:
        """Load keybindings, merging user overrides with defaults.

        Missing actions fall back to ``DEFAULT_BINDINGS``.  Unknown actions
        present in the user file are preserved.
        """
        merged = dict(DEFAULT_BINDINGS)
        user = self._read_file()
        if user:
            merged.update(user)
        return KeybindingConfig(bindings=merged)

    def save(self, bindings: KeybindingConfig) -> None:
        """Persist *bindings* to disk.

        Only writes keys that differ from the defaults so the file stays small.
        """
        overrides: dict[str, Any] = {}
        for action, key in bindings.bindings.items():
            if DEFAULT_BINDINGS.get(action) != key:
                overrides[action] = key
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(overrides, indent=2, ensure_ascii=False), encoding="utf-8")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _read_file(self) -> dict[str, str] | None:
        if not self._path.exists():
            return None
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return None
            return {str(k): str(v) for k, v in data.items()}
        except (json.JSONDecodeError, OSError):
            return None
