"""Auto-completion for the CLI.

Q55/369: fuzzy matching for slash commands (SequenceMatcher score ≥ 0.4).
Q55/370: @mention file auto-complete — @<path> completes project files.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document


def _fuzzy_score(query: str, candidate: str) -> float:
    """Return a similarity score in [0, 1] between query and candidate."""
    if not query:
        return 1.0
    q = query.lower()
    c = candidate.lower()
    if c.startswith(q):
        return 1.0
    if q in c:
        return 0.8
    return SequenceMatcher(None, q, c).ratio()


_FUZZY_THRESHOLD = 0.4


class LidcoCompleter(Completer):
    """Completer for slash commands, @agents/@files, and file paths.

    Q55/369: slash-command completion uses fuzzy matching so e.g. ``/com``
    matches ``/commit`` even without a leading prefix match.
    Q55/370: ``@<partial-path>`` completes project files via glob scan.
    """

    def __init__(
        self,
        command_meta: dict[str, str] | None = None,
        agent_names: list[str] | None = None,
        # Legacy parameter kept for backwards compatibility
        command_names: list[str] | None = None,
        project_dir: Path | None = None,
    ) -> None:
        if command_meta is not None:
            self._command_meta = command_meta
        elif command_names is not None:
            self._command_meta = {name: "command" for name in command_names}
        else:
            self._command_meta = {}
        self._agents = agent_names or []
        self._project_dir = project_dir or Path.cwd()

    def update_agents(self, names: list[str]) -> None:
        """Update available agent names."""
        self._agents = names

    def get_completions(
        self, document: Document, complete_event: Any
    ) -> Iterable[Completion]:
        text = document.text_before_cursor
        word = document.get_word_before_cursor(WORD=True)

        # Slash commands — Q55/369: fuzzy match
        if text.startswith("/"):
            # Task 168: context-aware completions after command name
            _agent_arg_cmds = {"as", "whois", "lock", "help"}
            for cmd in _agent_arg_cmds:
                prefix = f"/{cmd} "
                if text.startswith(prefix):
                    agent_prefix = text[len(prefix):]
                    candidates = (
                        self._agents if cmd != "help"
                        else list(self._command_meta.keys())
                    )
                    for name in sorted(candidates):
                        if name.startswith(agent_prefix):
                            meta = "agent" if cmd != "help" else "command"
                            yield Completion(
                                name + ("" if cmd == "help" else " "),
                                start_position=-len(agent_prefix),
                                display=name,
                                display_meta=meta,
                            )
                    return

            cmd_prefix = text[1:]
            # Build scored list; prefix matches first, then fuzzy
            scored: list[tuple[float, str, str]] = []
            for name, desc in self._command_meta.items():
                score = _fuzzy_score(cmd_prefix, name)
                if score >= _FUZZY_THRESHOLD:
                    scored.append((score, name, desc or "command"))
            for score, name, desc in sorted(scored, key=lambda x: (-x[0], x[1])):
                yield Completion(
                    name,
                    start_position=-len(cmd_prefix),
                    display=f"/{name}",
                    display_meta=desc,
                )
            return

        # @mention completion — Q55/370: files when @ prefix contains a path separator
        if text.startswith("@") and " " not in text:
            mention = text[1:]  # everything after @

            # If it looks like a file path (contains / \ or .) → file completion
            if "/" in mention or "\\" in mention or "." in mention:
                yield from self._complete_at_file(mention)
                return

            # Otherwise agent name completion
            for name in sorted(self._agents):
                if name.startswith(mention):
                    yield Completion(
                        name + " ",
                        start_position=-len(mention),
                        display=f"@{name}",
                        display_meta="agent",
                    )
            # Also show file suggestions that match
            yield from self._complete_at_file(mention)
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

    def _complete_at_file(self, partial: str) -> Iterable[Completion]:
        """Q55/370 — Complete project files for @<partial> mentions.

        Scans the project directory for Python/TS/JS files whose relative
        path fuzzy-matches *partial*.  Returns up to 20 suggestions.
        """
        try:
            base = self._project_dir
            if not base.exists():
                return

            skip = {".git", "node_modules", "__pycache__", "venv", ".venv", "dist", ".lidco"}
            ext = {".py", ".ts", ".js", ".tsx", ".jsx", ".yaml", ".yml", ".json", ".md"}
            count = 0

            for path in sorted(base.rglob("*")):
                if count >= 20:
                    break
                if any(part in skip for part in path.parts):
                    continue
                if path.is_dir():
                    continue
                if path.suffix not in ext:
                    continue
                rel = str(path.relative_to(base)).replace("\\", "/")
                score = _fuzzy_score(partial, rel)
                if score >= _FUZZY_THRESHOLD:
                    yield Completion(
                        rel + " ",
                        start_position=-len(partial),
                        display=f"@{rel}",
                        display_meta="file",
                    )
                    count += 1
        except (OSError, PermissionError):
            return
