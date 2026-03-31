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

    def register_async(self, name: str, description: str, handler: Callable[..., Awaitable[str]]) -> None:
        """Convenience: register a command from (name, description, handler) triple."""
        self.register(SlashCommand(name, description, handler))

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
        # Q91–Q100 command modules (register_qNN_commands pattern)
        from lidco.cli.commands import q91_cmds
        q91_cmds.register_q91_commands(self)
        from lidco.cli.commands import q92_cmds
        q92_cmds.register_q92_commands(self)
        from lidco.cli.commands import q93_cmds
        q93_cmds.register_q93_commands(self)
        from lidco.cli.commands import q94_cmds
        q94_cmds.register_q94_commands(self)
        from lidco.cli.commands import q95_cmds
        q95_cmds.register_q95_commands(self)
        from lidco.cli.commands import q96_cmds
        q96_cmds.register_q96_commands(self)
        from lidco.cli.commands import q97_cmds
        q97_cmds.register_q97_commands(self)
        from lidco.cli.commands import q98_cmds
        q98_cmds.register_q98_commands(self)
        from lidco.cli.commands import q99_cmds
        q99_cmds.register_q99_commands(self)
        from lidco.cli.commands import q100_cmds
        q100_cmds.register_q100_commands(self)
        # Q101–Q153 command modules (register pattern)
        from lidco.cli.commands import q101_cmds
        q101_cmds.register(self)
        from lidco.cli.commands import q102_cmds
        q102_cmds.register(self)
        from lidco.cli.commands import q103_cmds
        q103_cmds.register(self)
        from lidco.cli.commands import q104_cmds
        q104_cmds.register(self)
        from lidco.cli.commands import q105_cmds
        q105_cmds.register(self)
        from lidco.cli.commands import q106_cmds
        q106_cmds.register(self)
        from lidco.cli.commands import q107_cmds
        q107_cmds.register(self)
        from lidco.cli.commands import q108_cmds
        q108_cmds.register(self)
        from lidco.cli.commands import q109_cmds
        q109_cmds.register(self)
        from lidco.cli.commands import q110_cmds
        q110_cmds.register(self)
        from lidco.cli.commands import q111_cmds
        q111_cmds.register(self)
        from lidco.cli.commands import q112_cmds
        q112_cmds.register(self)
        from lidco.cli.commands import q113_cmds
        q113_cmds.register(self)
        from lidco.cli.commands import q114_cmds
        q114_cmds.register(self)
        from lidco.cli.commands import q115_cmds
        q115_cmds.register(self)
        from lidco.cli.commands import q116_cmds
        q116_cmds.register(self)
        from lidco.cli.commands import q117_cmds
        q117_cmds.register(self)
        from lidco.cli.commands import q118_cmds
        q118_cmds.register(self)
        from lidco.cli.commands import q119_cmds
        q119_cmds.register(self)
        from lidco.cli.commands import q120_cmds
        q120_cmds.register(self)
        from lidco.cli.commands import q121_cmds
        q121_cmds.register(self)
        from lidco.cli.commands import q122_cmds
        q122_cmds.register(self)
        from lidco.cli.commands import q123_cmds
        q123_cmds.register(self)
        from lidco.cli.commands import q124_cmds
        q124_cmds.register(self)
        from lidco.cli.commands import q125_cmds
        q125_cmds.register(self)
        from lidco.cli.commands import q126_cmds
        q126_cmds.register(self)
        from lidco.cli.commands import q127_cmds
        q127_cmds.register(self)
        from lidco.cli.commands import q128_cmds
        q128_cmds.register(self)
        from lidco.cli.commands import q129_cmds
        q129_cmds.register(self)
        from lidco.cli.commands import q130_cmds
        q130_cmds.register(self)
        from lidco.cli.commands import q131_cmds
        q131_cmds.register(self)
        from lidco.cli.commands import q132_cmds
        q132_cmds.register(self)
        from lidco.cli.commands import q133_cmds
        q133_cmds.register(self)
        from lidco.cli.commands import q134_cmds
        q134_cmds.register(self)
        from lidco.cli.commands import q135_cmds
        q135_cmds.register(self)
        from lidco.cli.commands import q136_cmds
        q136_cmds.register(self)
        from lidco.cli.commands import q137_cmds
        q137_cmds.register(self)
        from lidco.cli.commands import q138_cmds
        q138_cmds.register(self)
        from lidco.cli.commands import q139_cmds
        q139_cmds.register(self)
        from lidco.cli.commands import q140_cmds
        q140_cmds.register(self)
        from lidco.cli.commands import q141_cmds
        q141_cmds.register(self)
        from lidco.cli.commands import q142_cmds
        q142_cmds.register(self)
        from lidco.cli.commands import q143_cmds
        q143_cmds.register(self)
        from lidco.cli.commands import q144_cmds
        q144_cmds.register(self)
        from lidco.cli.commands import q145_cmds
        q145_cmds.register(self)
        from lidco.cli.commands import q146_cmds
        q146_cmds.register(self)
        from lidco.cli.commands import q147_cmds
        q147_cmds.register(self)
        from lidco.cli.commands import q148_cmds
        q148_cmds.register(self)
        from lidco.cli.commands import q149_cmds
        q149_cmds.register(self)
        from lidco.cli.commands import q150_cmds
        q150_cmds.register(self)
        from lidco.cli.commands import q151_cmds
        q151_cmds.register(self)
        from lidco.cli.commands import q152_cmds
        q152_cmds.register(self)
        from lidco.cli.commands import q153_cmds
        q153_cmds.register(self)
        from lidco.cli.commands import q160_cmds
        q160_cmds.register(self)
        from lidco.cli.commands import q161_cmds
        q161_cmds.register(self)
        from lidco.cli.commands import q162_cmds
        q162_cmds.register(self)
        from lidco.cli.commands import q163_cmds
        q163_cmds.register(self)
        from lidco.cli.commands import q164_cmds
        q164_cmds.register(self)
        from lidco.cli.commands import q165_cmds
        q165_cmds.register(self)
        from lidco.cli.commands import q166_cmds
        q166_cmds.register(self)
        from lidco.cli.commands import q167_cmds
        q167_cmds.register(self)
        from lidco.cli.commands import q168_cmds
        q168_cmds.register(self)
        from lidco.cli.commands import q169_cmds
        q169_cmds.register(self)
        from lidco.cli.commands import q170_cmds
        q170_cmds.register(self)
        from lidco.cli.commands import q172_cmds
        q172_cmds.register_q172_commands(self)
        from lidco.cli.commands import q173_cmds
        q173_cmds.register_q173_commands(self)
        from lidco.cli.commands import q175_cmds
        q175_cmds.register_q175_commands(self)
        from lidco.cli.commands import q176_cmds
        q176_cmds.register_q176_commands(self)
        from lidco.cli.commands import q179_cmds
        q179_cmds.register_q179_commands(self)
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
