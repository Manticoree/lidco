"""Q140 — HelpFormatter: structured help text formatting."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CommandHelp:
    """Help entry for a single command."""

    name: str
    description: str
    usage: str = ""
    examples: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)


class HelpFormatter:
    """Format help text for commands."""

    def __init__(self) -> None:
        self._commands: dict[str, CommandHelp] = {}

    def register(self, cmd: CommandHelp) -> None:
        self._commands[cmd.name] = cmd

    def format_command(self, name: str) -> str:
        """Detailed help for one command."""
        cmd = self._commands.get(name)
        if cmd is None:
            return f"Unknown command: {name}"
        lines = [
            f"/{cmd.name} — {cmd.description}",
        ]
        if cmd.usage:
            lines.append(f"\nUsage: {cmd.usage}")
        if cmd.aliases:
            lines.append(f"\nAliases: {', '.join(cmd.aliases)}")
        if cmd.examples:
            lines.append("\nExamples:")
            for ex in cmd.examples:
                lines.append(f"  {ex}")
        return "\n".join(lines)

    def format_list(self, filter_str: str = "") -> str:
        """List all commands, optionally filtered by substring."""
        filtered = sorted(self._commands.values(), key=lambda c: c.name)
        if filter_str:
            low = filter_str.lower()
            filtered = [
                c
                for c in filtered
                if low in c.name.lower() or low in c.description.lower()
            ]
        if not filtered:
            return "No commands found."
        lines = ["Available commands:"]
        for cmd in filtered:
            lines.append(f"  /{cmd.name:<20} {cmd.description}")
        return "\n".join(lines)

    def format_group(self, group_name: str, commands: list[str]) -> str:
        """Format a group header with listed commands."""
        lines = [f"=== {group_name} ==="]
        for name in commands:
            cmd = self._commands.get(name)
            if cmd:
                lines.append(f"  /{cmd.name:<20} {cmd.description}")
            else:
                lines.append(f"  /{name:<20} (not registered)")
        return "\n".join(lines)

    def search(self, query: str) -> list[CommandHelp]:
        """Search commands by name or description."""
        low = query.lower()
        results: list[CommandHelp] = []
        for cmd in self._commands.values():
            if low in cmd.name.lower() or low in cmd.description.lower():
                results.append(cmd)
        results.sort(key=lambda c: c.name)
        return results
