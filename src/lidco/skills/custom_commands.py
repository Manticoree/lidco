"""Custom slash commands from YAML — Task 296.

Loads ``.lidco/commands.yaml`` and ``~/.lidco/commands.yaml`` and registers
each entry as a slash command that runs a prompt template.

File format::

    commands:
      - name: review
        description: Review code for quality issues
        prompt: "Review the following for quality, bugs, and security: {args}"
        agent: reviewer

      - name: explain
        description: Explain code in simple terms
        prompt: "Explain this code in simple, clear terms: {args}"

Usage::

    loader = CustomCommandLoader(session)
    commands_list = loader.load()
    # → [CustomCommand(name="review", ...), ...]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_COMMAND_FILES = [
    Path.home() / ".lidco" / "commands.yaml",
    Path(".lidco") / "commands.yaml",
]


@dataclass
class CustomCommand:
    """A user-defined slash command."""

    name: str
    description: str = ""
    prompt: str = ""        # template; {args} substituted at runtime
    agent: str | None = None  # optional agent to route to

    def render(self, args: str = "") -> str:
        return self.prompt.replace("{args}", args).strip()


def load_custom_commands(
    extra_files: list[Path] | None = None,
) -> list[CustomCommand]:
    """Load custom commands from all standard locations.

    Later files override earlier entries with the same name.
    Returns a list of CustomCommand objects (deduped by name, last wins).
    """
    files = list(_COMMAND_FILES)
    if extra_files:
        files.extend(extra_files)

    seen: dict[str, CustomCommand] = {}
    for path in files:
        if not path.exists():
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            entries = data.get("commands") or []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("name", "")).lstrip("/").strip()
                if not name:
                    continue
                seen[name] = CustomCommand(
                    name=name,
                    description=str(entry.get("description", "")),
                    prompt=str(entry.get("prompt", "")),
                    agent=entry.get("agent") or None,
                )
            logger.debug("Loaded %d custom commands from %s", len(entries), path)
        except Exception as exc:
            logger.warning("Failed to load custom commands from %s: %s", path, exc)

    return list(seen.values())
