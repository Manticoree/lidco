"""Auto-completion for the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document


class LidcoCompleter(Completer):
    """Completer for slash commands, @agents, and file paths."""

    def __init__(
        self,
        command_meta: dict[str, str] | None = None,
        agent_names: list[str] | None = None,
        # Legacy parameter kept for backwards compatibility
        command_names: list[str] | None = None,
    ) -> None:
        if command_meta is not None:
            self._command_meta = command_meta
        elif command_names is not None:
            self._command_meta = {name: "command" for name in command_names}
        else:
            self._command_meta = {}
        self._agents = agent_names or []

    def update_agents(self, names: list[str]) -> None:
        """Update available agent names."""
        self._agents = names

    def get_completions(
        self, document: Document, complete_event: Any
    ) -> Iterable[Completion]:
        text = document.text_before_cursor
        word = document.get_word_before_cursor(WORD=True)

        # Slash commands
        if text.startswith("/"):
            cmd_prefix = text[1:]
            for name, desc in sorted(self._command_meta.items()):
                if name.startswith(cmd_prefix):
                    yield Completion(
                        name,
                        start_position=-len(cmd_prefix),
                        display=f"/{name}",
                        display_meta=desc or "command",
                    )
            return

        # @agent completion
        if text.startswith("@") and " " not in text:
            agent_prefix = text[1:]
            for name in sorted(self._agents):
                if name.startswith(agent_prefix):
                    yield Completion(
                        name + " ",
                        start_position=-len(agent_prefix),
                        display=f"@{name}",
                        display_meta="agent",
                    )
            return

        # File path completion (after certain keywords)
        path_triggers = ("read ", "edit ", "open ", "file ", "path ")
        for trigger in path_triggers:
            if text.lower().endswith(trigger) or (word and "/" in word):
                yield from self._complete_path(word or "")
                return

    def _complete_path(self, prefix: str) -> Iterable[Completion]:
        """Complete file paths."""
        try:
            if not prefix:
                search_dir = Path.cwd()
                prefix_path = Path("")
            else:
                prefix_path = Path(prefix)
                if prefix_path.is_dir():
                    search_dir = prefix_path
                else:
                    search_dir = prefix_path.parent or Path.cwd()

            if not search_dir.exists():
                return

            skip = {".git", "node_modules", "__pycache__", "venv", ".venv", "dist"}
            count = 0

            for item in sorted(search_dir.iterdir()):
                if item.name.startswith(".") and item.name not in (".env",):
                    continue
                if item.name in skip:
                    continue
                if count >= 50:
                    break

                name = str(item.relative_to(search_dir))
                if item.is_dir():
                    name += "/"

                if not prefix or name.startswith(prefix_path.name):
                    yield Completion(
                        name,
                        start_position=-len(prefix_path.name) if prefix else 0,
                        display=name,
                        display_meta="dir" if item.is_dir() else "file",
                    )
                    count += 1
        except (OSError, PermissionError):
            return
