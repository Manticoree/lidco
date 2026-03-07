"""Persistent user preferences stored in ~/.lidco/prefs.json.

Lightweight key/value store for cross-session UI state (hint counters,
feature flags, etc.).  Not intended for project-level configuration —
use config.yaml for that.
"""

from __future__ import annotations

import json
from pathlib import Path


_DEFAULT_PATH = Path.home() / ".lidco" / "prefs.json"
_MAX_HINT_SHOWS = 3


class PrefsStore:
    """Read/write user preferences from a JSON file.

    All mutations are immediately flushed to disk so preferences survive
    crashes and keyboard-interrupt exits.

    Args:
        path: Override the default ``~/.lidco/prefs.json`` path (for tests).
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _DEFAULT_PATH
        self._data: dict = self._load()

    # ── persistence ──────────────────────────────────────────────────────────

    def _load(self) -> dict:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass  # prefs are best-effort; never crash the app over them

    # ── generic API ──────────────────────────────────────────────────────────

    def get(self, key: str, default: object = None) -> object:
        """Return stored value for *key*, or *default* if absent."""
        return self._data.get(key, default)

    def set(self, key: str, value: object) -> None:
        """Store *value* under *key* and flush to disk."""
        self._data[key] = value
        self._save()

    # ── newline hint ─────────────────────────────────────────────────────────

    def should_show_newline_hint(self) -> bool:
        """Return True while the multiline hint has been shown fewer than MAX times."""
        count = int(self._data.get("newline_hint_shown", 0))
        return count < _MAX_HINT_SHOWS

    def record_newline_hint_shown(self) -> None:
        """Increment the hint-show counter and persist."""
        count = int(self._data.get("newline_hint_shown", 0))
        self._data["newline_hint_shown"] = count + 1
        self._save()
