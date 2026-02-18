"""Slash commands for the CLI."""

from __future__ import annotations

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
        registry = self

        async def help_handler(**_: Any) -> str:
            lines = [
                "**Available commands:**",
                "",
                "| Command | Description |",
                "|---------|-------------|",
            ]
            for cmd in sorted(registry._commands.values(), key=lambda c: c.name):
                lines.append(f"| `/{cmd.name}` | {cmd.description} |")
            lines.append("")
            lines.append("**Tip:** Use `@agent_name message` to target a specific agent.")
            return "\n".join(lines)

        async def model_handler(arg: str = "", **_: Any) -> str:
            if not arg:
                current = ""
                if registry._session:
                    current = registry._session.config.llm.default_model
                return f"Current model: **{current}**\n\nUsage: `/model <model_name>`\n\nExamples: `gpt-4o`, `claude-sonnet-4-5-20250514`, `ollama/llama3.1`, `groq/llama-3.1-70b-versatile`"
            if registry._session:
                registry._session.config.llm.default_model = arg
            return f"Switched to model: **{arg}**"

        async def agents_handler(**_: Any) -> str:
            if not registry._session:
                return "Session not initialized."
            names = registry._session.agent_registry.list_names()
            agents = registry._session.agent_registry.list_agents()
            lines = ["**Available agents:**", ""]
            for agent in agents:
                lines.append(f"- **{agent.name}**: {agent.description}")
            lines.append("")
            lines.append("Use `@agent_name message` to target a specific agent.")
            return "\n".join(lines)

        async def memory_handler(arg: str = "", **_: Any) -> str:
            if not registry._session:
                return "Session not initialized."
            mem = registry._session.memory
            if arg.startswith("add "):
                # /memory add key: content
                rest = arg[4:].strip()
                if ":" not in rest:
                    return "Usage: `/memory add key: content`"
                key, content = rest.split(":", 1)
                mem.add(key=key.strip(), content=content.strip(), category="manual")
                return f"Saved memory: **{key.strip()}**"
            if arg.startswith("search "):
                query = arg[7:].strip()
                results = mem.search(query)
                if not results:
                    return "No memories found."
                lines = [f"**Found {len(results)} memories:**", ""]
                for r in results:
                    lines.append(f"- **{r.key}** [{r.category}]: {r.content[:100]}")
                return "\n".join(lines)
            if arg == "list":
                entries = mem.list_all()
                if not entries:
                    return "No memories stored."
                lines = [f"**{len(entries)} memories:**", ""]
                for e in entries:
                    lines.append(f"- **{e.key}** [{e.category}]: {e.content[:80]}")
                return "\n".join(lines)
            return (
                "**Memory commands:**\n\n"
                "- `/memory list` - Show all memories\n"
                "- `/memory add key: content` - Add a memory\n"
                "- `/memory search query` - Search memories"
            )

        async def context_handler(**_: Any) -> str:
            if not registry._session:
                return "Session not initialized."
            ctx = registry._session.get_full_context()
            if not ctx:
                return "No project context available."
            # Truncate for display
            if len(ctx) > 3000:
                ctx = ctx[:3000] + "\n\n... (truncated)"
            return f"**Current context:**\n\n```\n{ctx}\n```"

        async def clear_handler(**_: Any) -> str:
            if registry._session:
                registry._session.orchestrator.clear_history()
            return "__CLEAR__"

        async def export_handler(arg: str = "", **_: Any) -> str:
            if not registry._session:
                return "Session not initialized."

            history = registry._session.orchestrator._conversation_history
            if not history:
                return "No conversation to export."

            from datetime import datetime

            now = datetime.now()
            model = registry._session.config.llm.default_model
            cwd = str(Path.cwd())

            lines = [
                "# LIDCO Session Export",
                "",
                f"- **Date:** {now.strftime('%Y-%m-%d %H:%M:%S')}",
                f"- **Model:** {model}",
                f"- **Directory:** {cwd}",
                "",
                "---",
                "",
            ]

            for msg in history:
                role = msg["role"]
                content = msg["content"]
                if role == "user":
                    lines.append(f"## You\n\n{content}\n")
                else:
                    lines.append(f"## LIDCO\n\n{content}\n")

            md_content = "\n".join(lines)

            if arg.strip():
                output_path = Path(arg.strip())
            else:
                timestamp = now.strftime("%Y%m%d-%H%M%S")
                output_path = Path(f"lidco-session-{timestamp}.md")

            output_path.write_text(md_content, encoding="utf-8")
            return f"Session exported to `{output_path}` ({len(history)} messages)"

        async def exit_handler(**_: Any) -> str:
            return "__EXIT__"

        async def init_handler(arg: str = "", **_: Any) -> str:
            from lidco.core.rules import RulesManager

            rules_mgr = RulesManager()
            if rules_mgr.has_rules_file():
                return (
                    f"**LIDCO.md** already exists at `{rules_mgr.rules_file}`.\n\n"
                    "Use `/rules` to view or add rules."
                )

            project_name = arg.strip() if arg.strip() else None
            try:
                path = rules_mgr.init_rules(project_name=project_name)
            except OSError as e:
                return f"Failed to create rules file: {e}"

            return (
                f"Created **LIDCO.md** at `{path}`\n\n"
                f"Also created `.lidco/rules/` directory for additional rule files.\n\n"
                "Edit `LIDCO.md` directly or use:\n"
                "- `/rules add Title: description` - append a rule to LIDCO.md\n"
                "- `/rules file name: content` - create a separate rule file\n"
                "- `/rules list` - show all current rules"
            )

        async def rules_handler(arg: str = "", **_: Any) -> str:
            from lidco.core.rules import RulesManager

            rules_mgr = RulesManager()

            if not arg or arg.strip() == "help":
                return (
                    "**Rules commands:**\n\n"
                    "- `/rules list` - List all rules from LIDCO.md\n"
                    "- `/rules add Title: description` - Append a rule to LIDCO.md\n"
                    "- `/rules file name: content` - Create a separate .lidco/rules/name.md file\n"
                    "- `/rules show` - Show full rules text\n"
                    "- `/rules files` - List rule files in .lidco/rules/"
                )

            if arg.strip() == "list":
                rules = rules_mgr.list_rules()
                if not rules:
                    return "No rules defined. Use `/init` to create LIDCO.md."
                lines = [f"**{len(rules)} rules in LIDCO.md:**", ""]
                for rule in rules:
                    preview = rule.content[:100].replace("\n", " ")
                    lines.append(f"- **{rule.title}**: {preview}")
                return "\n".join(lines)

            if arg.strip() == "show":
                text = rules_mgr.get_all_rules_text()
                if not text:
                    return "No rules defined. Use `/init` to create LIDCO.md."
                if len(text) > 4000:
                    text = text[:4000] + "\n\n... (truncated)"
                return f"```markdown\n{text}\n```"

            if arg.strip() == "files":
                files = rules_mgr.list_rule_files()
                if not files:
                    return "No additional rule files in `.lidco/rules/`."
                lines = [f"**{len(files)} rule files:**", ""]
                for f in files:
                    lines.append(f"- `{f.name}`")
                return "\n".join(lines)

            if arg.startswith("add "):
                rest = arg[4:].strip()
                if ":" not in rest:
                    return "Usage: `/rules add Title: rule description`"
                title, content = rest.split(":", 1)
                title = title.strip()
                content = content.strip()
                if not title or not content:
                    return "Both title and content are required."
                try:
                    rules_mgr.add_rule(title, content)
                except OSError as e:
                    return f"Failed to add rule: {e}"
                return f"Added rule **{title}** to LIDCO.md"

            if arg.startswith("file "):
                rest = arg[5:].strip()
                if ":" not in rest:
                    return "Usage: `/rules file name: rule content`"
                name, content = rest.split(":", 1)
                name = name.strip()
                content = content.strip()
                if not name or not content:
                    return "Both name and content are required."
                try:
                    path = rules_mgr.add_rule_file(name, content)
                except OSError as e:
                    return f"Failed to create rule file: {e}"
                return f"Created rule file at `{path}`"

            return "Unknown rules sub-command. Use `/rules help` for usage."

        async def decisions_handler(arg: str = "", **_: Any) -> str:
            if not registry._session:
                return "Session not initialized."
            mgr = registry._session.clarification_mgr

            if not arg or arg.strip() == "list":
                entries = mgr.list_recent(20)
                if not entries:
                    return "No decisions recorded yet."
                lines = [f"**{len(entries)} recent decisions:**", ""]
                for e in entries:
                    ts = e.timestamp[:10] if e.timestamp else "?"
                    lines.append(f"- [{ts}] **{e.question}** → {e.answer}")
                return "\n".join(lines)

            if arg.startswith("search "):
                query = arg[7:].strip()
                if not query:
                    return "Usage: `/decisions search <query>`"
                entries = mgr.find_relevant(query, limit=10)
                if not entries:
                    return f"No decisions found for '{query}'."
                lines = [f"**Found {len(entries)} decisions:**", ""]
                for e in entries:
                    lines.append(f"- **{e.question}** → {e.answer}")
                return "\n".join(lines)

            if arg.strip() == "clear":
                count = mgr.clear()
                return f"Cleared **{count}** decision(s)."

            return (
                "**Decisions commands:**\n\n"
                "- `/decisions` or `/decisions list` - Show recent decisions\n"
                "- `/decisions search <query>` - Search decisions\n"
                "- `/decisions clear` - Clear decision history"
            )

        async def index_handler(arg: str = "", **_: Any) -> str:
            import asyncio

            if not registry._session:
                return "Session not initialized."

            project_dir = registry._session.project_dir
            db_path = project_dir / ".lidco" / "project_index.db"

            from lidco.index.db import IndexDatabase
            from lidco.index.project_indexer import ProjectIndexer

            mode = arg.strip().lower()
            if mode not in ("", "full", "incremental"):
                return (
                    "**Usage:** `/index [full|incremental]`\n\n"
                    "- `/index` — smart (incremental if already indexed, full otherwise)\n"
                    "- `/index full` — rebuild index from scratch\n"
                    "- `/index incremental` — only re-index changed files"
                )

            def _run() -> str:
                db = IndexDatabase(db_path)
                try:
                    indexer = ProjectIndexer(project_dir=project_dir, db=db)

                    # Decide mode
                    use_full = (
                        mode == "full"
                        or (mode == "" and indexer.is_stale(max_age_hours=0))
                    )

                    progress: list[str] = []

                    def _cb(i: int, n: int, name: str) -> None:
                        progress.append(name)

                    if use_full:
                        result = indexer.run_full_index(progress_callback=_cb)
                        run_mode = "Full"
                    else:
                        result = indexer.run_incremental_index(progress_callback=_cb)
                        run_mode = "Incremental"

                    # Refresh session enricher with a fresh connection to the updated DB
                    from lidco.index.context_enricher import IndexContextEnricher
                    registry._session.index_enricher = (
                        IndexContextEnricher.from_project_dir(project_dir)
                    )

                    s = result.stats
                    lines = [
                        f"**{run_mode} index complete**",
                        "",
                        f"- Added: {result.added}  Updated: {result.updated}  "
                        f"Deleted: {result.deleted}  Skipped: {result.skipped}",
                        f"- Total: **{s.total_files} files** · {s.total_symbols} symbols "
                        f"· {s.total_imports} imports",
                    ]
                    if s.files_by_language:
                        lang_str = ", ".join(
                            f"{cnt} {lang}"
                            for lang, cnt in sorted(s.files_by_language.items(), key=lambda x: -x[1])
                        )
                        lines.append(f"- Languages: {lang_str}")
                    lines.append("")
                    lines.append("_Structural context is now active for this session._")
                    return "\n".join(lines)
                finally:
                    db.close()

            return await asyncio.get_event_loop().run_in_executor(None, _run)

        async def index_status_handler(**_: Any) -> str:
            import asyncio

            if not registry._session:
                return "Session not initialized."

            project_dir = registry._session.project_dir
            db_path = project_dir / ".lidco" / "project_index.db"

            if not db_path.exists():
                return (
                    "**No index found.**\n\n"
                    "Run `/index` to build the structural index for this project."
                )

            from lidco.index.db import IndexDatabase
            from lidco.index.project_indexer import ProjectIndexer

            def _run() -> str:
                db = IndexDatabase(db_path)
                try:
                    indexer = ProjectIndexer(project_dir=project_dir, db=db)
                    s = db.get_stats()

                    import datetime

                    lines = ["**Project Index Status**", ""]

                    if s.last_indexed_at:
                        dt = datetime.datetime.fromtimestamp(
                            s.last_indexed_at, tz=datetime.timezone.utc
                        )
                        lines.append(f"- **Last indexed:** {dt.strftime('%Y-%m-%d %H:%M')} UTC")
                    else:
                        lines.append("- **Last indexed:** never")

                    lines += [
                        f"- **Files:** {s.total_files}",
                        f"- **Symbols:** {s.total_symbols}",
                        f"- **Imports:** {s.total_imports}",
                    ]

                    if s.files_by_language:
                        lang_str = ", ".join(
                            f"{cnt} {lang}"
                            for lang, cnt in sorted(s.files_by_language.items(), key=lambda x: -x[1])
                        )
                        lines.append(f"- **Languages:** {lang_str}")

                    if s.files_by_role:
                        role_str = ", ".join(
                            f"{cnt} {role}"
                            for role, cnt in sorted(s.files_by_role.items(), key=lambda x: -x[1])
                            if cnt > 0
                        )
                        lines.append(f"- **Roles:** {role_str}")

                    stale = indexer.is_stale(max_age_hours=24)
                    new_files = indexer.has_new_files()
                    if stale:
                        lines.append("\n_Index is older than 24 hours — consider running `/index`._")
                    elif new_files:
                        lines.append("\n_New files detected — run `/index incremental` to update._")
                    else:
                        lines.append("\n_Index is up to date._")

                    return "\n".join(lines)
                finally:
                    db.close()

            return await asyncio.get_event_loop().run_in_executor(None, _run)

        async def config_handler(arg: str = "", **_: Any) -> str:
            if not registry._session:
                return "Session not initialized."

            from io import StringIO
            from rich.console import Console as RichConsole
            from rich.table import Table

            cfg = registry._session.config

            if not arg or arg.strip() == "show":
                table = Table(title="lidco config", show_header=True, header_style="bold cyan")
                table.add_column("Setting", style="cyan")
                table.add_column("Value", style="green")
                table.add_column("Description", style="dim")

                table.add_row("llm.default_model", cfg.llm.default_model, "Active LLM model")
                table.add_row("llm.streaming", str(cfg.llm.streaming), "Stream responses token by token")
                table.add_row(
                    "memory.enabled",
                    str(getattr(cfg.memory, "enabled", False)),
                    "RAG memory",
                )
                table.add_row(
                    "memory.auto_save",
                    str(getattr(cfg.memory, "auto_save", False)),
                    "Auto-save to memory after tool calls",
                )
                table.add_row(
                    "cli.show_tool_calls",
                    str(getattr(cfg.cli, "show_tool_calls", False)),
                    "Show tool calls in non-streaming mode",
                )

                buf = StringIO()
                tmp_console = RichConsole(file=buf, force_terminal=False, width=100)
                tmp_console.print(table)
                return f"```\n{buf.getvalue().strip()}\n```"

            parts = arg.strip().split()
            if parts[0] == "set" and len(parts) >= 3:
                key = parts[1]
                value = " ".join(parts[2:])

                if key == "model":
                    cfg.llm.default_model = value
                    return f"Set **llm.default_model** = `{value}`"

                if key == "streaming":
                    if value.lower() in ("on", "true", "1", "yes"):
                        cfg.llm.streaming = True
                        return "Streaming **enabled**."
                    elif value.lower() in ("off", "false", "0", "no"):
                        cfg.llm.streaming = False
                        return "Streaming **disabled**."
                    return f"Unknown value '{value}'. Use `on` or `off`."

                if key == "show_tool_calls":
                    if value.lower() in ("on", "true", "1", "yes"):
                        cfg.cli.show_tool_calls = True
                        return "Tool call display **enabled**."
                    elif value.lower() in ("off", "false", "0", "no"):
                        cfg.cli.show_tool_calls = False
                        return "Tool call display **disabled**."
                    return f"Unknown value '{value}'. Use `on` or `off`."

                return f"Unknown config key: `{key}`. Available: `model`, `streaming`, `show_tool_calls`."

            return (
                "**Config commands:**\n\n"
                "- `/config` — show current configuration\n"
                "- `/config set model <name>` — change the active LLM model\n"
                "- `/config set streaming on|off` — enable/disable streaming\n"
                "- `/config set show_tool_calls on|off` — show/hide tool calls"
            )

        self.register(SlashCommand("help", "Show available commands", help_handler))
        self.register(SlashCommand("model", "Switch or show current LLM model", model_handler))
        self.register(SlashCommand("agents", "List available agents", agents_handler))
        self.register(SlashCommand("memory", "Manage persistent memory", memory_handler))
        self.register(SlashCommand("context", "Show current project context", context_handler))
        self.register(SlashCommand("index", "Build/update the structural project index", index_handler))
        self.register(SlashCommand("index-status", "Show current index statistics", index_status_handler))
        self.register(SlashCommand("init", "Initialize LIDCO.md rules file", init_handler))
        self.register(SlashCommand("rules", "Manage project rules", rules_handler))
        self.register(SlashCommand("decisions", "Manage clarification decisions", decisions_handler))
        self.register(SlashCommand("export", "Export session to Markdown", export_handler))
        self.register(SlashCommand("clear", "Clear conversation history", clear_handler))
        self.register(SlashCommand("config", "Show or set runtime configuration", config_handler))
        self.register(SlashCommand("exit", "Exit LIDCO", exit_handler))
