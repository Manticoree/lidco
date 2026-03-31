"""User-configurable model aliases -- Q162."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_DEFAULT_ALIASES: dict[str, str] = {
    "s": "anthropic/claude-sonnet-4-6",
    "o": "anthropic/claude-opus-4-6",
    "h": "anthropic/claude-haiku-4-5",
}


class ModelAliasRegistry:
    """Map short alias names to full model identifiers.

    Comes pre-loaded with sensible defaults and supports JSON persistence
    so users can save / restore their custom aliases.
    """

    def __init__(self, aliases: dict[str, str] | None = None) -> None:
        if aliases is not None:
            self._aliases: dict[str, str] = dict(aliases)
        else:
            self._aliases = dict(_DEFAULT_ALIASES)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, alias: str, model: str) -> None:
        """Register *alias* as a short name for *model*."""
        self._aliases = {**self._aliases, alias: model}

    def remove(self, alias: str) -> bool:
        """Remove *alias*. Return ``True`` if it existed."""
        if alias not in self._aliases:
            return False
        self._aliases = {k: v for k, v in self._aliases.items() if k != alias}
        return True

    def resolve(self, name_or_alias: str) -> str:
        """Return the full model name for *name_or_alias*.

        If *name_or_alias* is a known alias the mapped model string is
        returned; otherwise the input is returned unchanged.
        """
        return self._aliases.get(name_or_alias, name_or_alias)

    def list(self) -> dict[str, str]:
        """Return a copy of all registered aliases."""
        return dict(self._aliases)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Persist aliases to a JSON file at *path*."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self._aliases, indent=2), encoding="utf-8")

    def load(self, path: str) -> None:
        """Load aliases from a JSON file at *path*."""
        p = Path(path)
        if not p.is_file():
            return
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            self._aliases = {str(k): str(v) for k, v in data.items()}
