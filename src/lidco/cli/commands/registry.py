"""Slash commands for the CLI."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Awaitable


@dataclass(frozen=True)
class SlashCommand:
    """A slash command definition."""

    name: str
    description: str
    handler: Callable[..., Awaitable[str]]


class CommandRegistry:
    """Registry for slash commands."""

    def __init__(self) -> None:
        self._commands: dict[str, SlashCommand] = {}
        self._session: Any = None
        self.last_message: str = ""           # set by app.py after each user turn
        self.locked_agent: str | None = None  # Task 152: /lock <agent>
        self.session_note: str = ""           # Task 167: /note sticky context
        self._aliases: dict[str, str] = {}    # Task 169: /alias
        self._edited_files: deque[str] = deque(maxlen=200)  # Task 171: /recent tracking (Q54/366)
        self.focus_file: str = ""             # Task 172: /focus sticky file
        self._pins: list[str] = []            # Task 173: /pin persistent context
        self._vars: dict[str, str] = {}       # Task 174: /vars template substitution
        self._turn_times: deque[float] = deque(maxlen=500)  # Task 175: /timing (Q54/366)
        self._snapshots: dict[str, list] = {} # Task 177: /snapshot named history saves
        self._watched_files: list[str] = []   # Task 179: /watch tracked paths
        self._watch_snapshot: dict[str, float] = {}  # Task 179: mtime baseline
        self._tags: dict[str, int] = {}       # Task 180: /tag turn labels
        self._agent_stats: dict[str, dict] = {}  # Task 182: /profile per-agent stats
        self._templates: dict[str, str] = {}  # Task 183: /template message templates
        self.session_mode: str = "normal"      # Task 185: /mode conversation mode
        self._autosave_interval: int = 0       # Task 186: /autosave turns between saves (0=off)
        self._autosave_turn_count: int = 0     # Task 186: turns elapsed counter
        self._reminders: list[dict] = []       # Task 187: /remind scheduled reminders
        self._bookmarks: dict[str, dict] = {} # Task 188: /bookmark file+line positions
        self._register_builtins()

    def set_session(self, session: Any) -> None:
        """Bind session for commands that need it."""
        self._session = session

    def register(self, cmd: SlashCommand) -> None:
        self._commands[cmd.name] = cmd

    def get(self, name: str) -> SlashCommand | None:
        return self._commands.get(name)

    def list_commands(self) -> list[SlashCommand]:
        return list(self._commands.values())

    def _register_builtins(self) -> None:
        """Register all built-in slash commands by delegating to domain modules."""
        from lidco.cli.commands import (
            core,
            session,
            tools_cmds,
            utils_cmds,
            context_cmds,
            agents_cmds,
            git_cmds,
            runtime_cmds,
            spec_cmds,
            wiki_cmds,
        )
        core.register(self)
        session.register(self)
        tools_cmds.register(self)
        utils_cmds.register(self)
        context_cmds.register(self)
        agents_cmds.register(self)
        git_cmds.register(self)
        runtime_cmds.register(self)
        spec_cmds.register(self)  # Q68 — overrides Q42 /spec with full pipeline
        wiki_cmds.register(self)  # Q69 — /wiki and /ask
        from lidco.cli.commands import transform_cmds
        transform_cmds.register_transform_commands(self)
        from lidco.cli.commands import intelligence_cmds
        intelligence_cmds.register_intelligence_commands(self)
        from lidco.cli.commands import learning_cmds
        learning_cmds.register_learning_commands(self)
        from lidco.cli.commands import platform_cmds
        platform_cmds.register_platform_commands(self)
        from lidco.cli.commands import nav_cmds
        nav_cmds.register_nav_commands(self)
        from lidco.cli.commands import graph_cmds
        graph_cmds.register_graph_commands(self)
        from lidco.cli.commands import browser_cmds
        browser_cmds.register_browser_commands(self)
        from lidco.cli.commands import turbo_cmds
        turbo_cmds.register_turbo_commands(self)
        self._load_skill_commands()

    def _load_skill_commands(self) -> None:
        """Register discovered skills and custom commands as slash commands."""
        # Custom commands from .lidco/commands.yaml (Task 296)
        try:
            from lidco.skills.custom_commands import load_custom_commands
            for cmd in load_custom_commands():
                if self._commands.get(cmd.name):
                    continue  # don't override built-ins

                # Use a closure to capture cmd correctly
                def _register_custom(c: Any) -> None:
                    async def _h(arg: str = "", **kw: Any) -> str:
                        session = self._session
                        prompt = c.render(arg)
                        if not prompt:
                            return f"Custom command `/{c.name}` has no prompt."
                        try:
                            response = await session.orchestrator.handle(prompt, agent_name=c.agent)
                            return response.content if hasattr(response, "content") else str(response)
                        except Exception as exc:
                            return f"/{c.name} failed: {exc}"
                    desc = c.description or f"Custom command: {c.name}"
                    self.register(SlashCommand(c.name, desc, _h))

                _register_custom(cmd)
        except Exception:
            pass  # custom commands are optional
