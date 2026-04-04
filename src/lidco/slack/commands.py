"""CommandBridge — receive and execute Slack commands (stdlib only)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class ParsedMention:
    """Result of parsing an @mention command."""
    command: str
    args: str


class CommandBridge:
    """Bridge between Slack @mentions and internal command handlers.

    Parameters
    ----------
    prefix:
        Mention prefix to detect.  Default ``"@lidco"``.
    """

    def __init__(self, prefix: str = "@lidco") -> None:
        self._prefix = prefix
        self._handlers: dict[str, Callable[[str], str]] = {}
        self._default_handler: Callable[[str], str] | None = None

    # ---------------------------------------------------------- register

    def register_handler(self, cmd: str, handler: Callable[[str], str]) -> None:
        """Register *handler* for the given *cmd* name."""
        if not cmd:
            raise ValueError("cmd must not be empty")
        if handler is None:
            raise ValueError("handler must not be None")
        self._handlers = {**self._handlers, cmd: handler}

    def set_default_handler(self, handler: Callable[[str], str]) -> None:
        """Set a fallback handler for unknown commands."""
        self._default_handler = handler

    # ------------------------------------------------------------ parse

    def parse_mention(self, text: str) -> tuple[str, str]:
        """Parse a mention string into ``(command, args)`` tuple.

        Returns ``("", "")`` if the text does not start with the prefix.
        """
        if not text:
            return ("", "")
        stripped = text.strip()
        if not stripped.lower().startswith(self._prefix.lower()):
            return ("", "")
        remainder = stripped[len(self._prefix):].strip()
        if not remainder:
            return ("help", "")
        parts = remainder.split(None, 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        return (cmd, args)

    # ---------------------------------------------------------- execute

    def execute(self, command: str) -> str:
        """Execute a raw mention string and return the response text."""
        cmd, args = self.parse_mention(command)
        if not cmd:
            return "Error: not a valid mention command."
        handler = self._handlers.get(cmd)
        if handler is not None:
            try:
                return handler(args)
            except Exception as exc:
                return f"Error executing '{cmd}': {exc}"
        if self._default_handler is not None:
            return self._default_handler(f"{cmd} {args}".strip())
        return f"Unknown command: {cmd}"

    # ------------------------------------------------------------ list

    def list_commands(self) -> list[str]:
        """Return sorted list of registered command names."""
        return sorted(self._handlers.keys())
