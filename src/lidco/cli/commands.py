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
                return f"Current model: **{current}**\n\nUsage: `/model <model_name>`\n\nExample: `openai/glm-4.7`"
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
            ctx = registry._session.get_full_context(skip_dedup=True)
            if not ctx:
                return "No project context available."
            # Truncate for display
            if len(ctx) > 3000:
                ctx = ctx[:3000] + "\n\n... (truncated)"
            return f"**Current context:**\n\n```\n{ctx}\n```"

        async def clear_handler(**_: Any) -> str:
            if registry._session:
                registry._session.orchestrator.clear_history()
                registry._session.clear_context_cache()
            return "__CLEAR__"

        async def export_handler(arg: str = "", **_: Any) -> str:
            if not registry._session:
                return "Session not initialized."

            history = registry._session.orchestrator._conversation_history
            if not history:
                return "No conversation to export."

            import importlib.metadata
            import json
            from datetime import datetime

            now = datetime.now()
            model = registry._session.config.llm.default_model
            cwd = str(Path.cwd())

            try:
                lidco_version = importlib.metadata.version("lidco")
            except importlib.metadata.PackageNotFoundError:
                lidco_version = "unknown"

            # Parse flags and optional path from arg
            parts = arg.split() if arg else []
            use_md = "--md" in parts
            path_parts = [p for p in parts if p != "--md"]
            explicit_path = path_parts[0] if path_parts else ""

            # Collect token / cost metadata if available
            tb = getattr(registry._session, "token_budget", None)
            tokens: dict[str, int] = {}
            cost_usd = 0.0
            if tb is not None:
                tokens = {
                    "prompt": getattr(tb, "total_prompt_tokens", 0),
                    "completion": getattr(tb, "total_completion_tokens", 0),
                    "total": (
                        getattr(tb, "total_prompt_tokens", 0)
                        + getattr(tb, "total_completion_tokens", 0)
                    ),
                }
                cost_usd = getattr(tb, "total_cost_usd", 0.0)

            if use_md:
                # ── Markdown format ──────────────────────────────────────────
                lines = [
                    "# LIDCO Session Export",
                    "",
                    f"- **Date:** {now.strftime('%Y-%m-%d %H:%M:%S')}",
                    f"- **Model:** {model}",
                    f"- **Directory:** {cwd}",
                ]
                if tokens:
                    lines.append(
                        f"- **Tokens:** {tokens['total']:,}"
                        f" ({tokens['prompt']:,} in / {tokens['completion']:,} out)"
                    )
                if cost_usd:
                    lines.append(f"- **Cost:** ~${cost_usd:.4f}")
                lines += ["", "---", ""]

                for msg in history:
                    role = msg["role"]
                    content = msg["content"]
                    if role == "user":
                        lines.append(f"## You\n\n{content}\n")
                    else:
                        lines.append(f"## LIDCO\n\n{content}\n")

                content_str = "\n".join(lines)
                if explicit_path:
                    output_path = Path(explicit_path)
                else:
                    timestamp = now.strftime("%Y%m%d-%H%M%S")
                    output_path = Path(f"lidco-session-{timestamp}.md")

                output_path.write_text(content_str, encoding="utf-8")
            else:
                # ── JSON format (default) ─────────────────────────────────────
                payload: dict[str, Any] = {
                    "lidco_version": lidco_version,
                    "exported_at": now.isoformat(),
                    "model": model,
                    "project_dir": cwd,
                    "tokens": tokens,
                    "cost_usd": cost_usd,
                    "messages": list(history),
                }
                content_str = json.dumps(payload, ensure_ascii=False, indent=2)

                if explicit_path:
                    output_path = Path(explicit_path)
                else:
                    exports_dir = Path(".lidco") / "exports"
                    exports_dir.mkdir(parents=True, exist_ok=True)
                    timestamp = now.strftime("%Y%m%d-%H%M%S")
                    output_path = exports_dir / f"session-{timestamp}.json"

                output_path.write_text(content_str, encoding="utf-8")

            return f"Session exported to `{output_path}` ({len(history)} messages)"

        async def import_handler(arg: str = "", **_: Any) -> str:
            if not registry._session:
                return "Session not initialized."

            import json

            path_str = arg.strip()
            if not path_str:
                return (
                    "Usage: `/import <path>`\n"
                    "Restores a previously exported JSON session.\n"
                    "Example: `/import .lidco/exports/session-20250115-103000.json`"
                )

            import_path = Path(path_str)
            if not import_path.exists():
                return f"File not found: `{import_path}`"

            try:
                data = json.loads(import_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                return f"Failed to read export file: {e}"

            if "messages" not in data or not isinstance(data["messages"], list):
                return (
                    "Invalid export file: missing 'messages' key. "
                    "Only LIDCO JSON exports can be imported."
                )

            messages: list[dict[str, str]] = [
                m for m in data["messages"]
                if isinstance(m, dict) and "role" in m and "content" in m
            ]
            if not messages:
                return "Export file contains no valid messages."

            registry._session.orchestrator.restore_history(messages)

            # Build summary line
            exported_at = data.get("exported_at", "unknown date")
            export_model = data.get("model", "unknown model")
            tokens = data.get("tokens", {})
            token_str = (
                f", {tokens.get('total', 0):,} tokens" if tokens else ""
            )

            return (
                f"Imported {len(messages)} messages from `{import_path}`\n"
                f"- Exported: {exported_at}\n"
                f"- Model: {export_model}{token_str}\n\n"
                "Conversation history restored. New messages will continue from here."
            )

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

        async def plan_handler(arg: str = "", **_: Any) -> str:
            if not registry._session:
                return "Session not initialized."
            if not arg.strip():
                return (
                    "**Usage:** `/plan <task description>`\n\n"
                    "Runs the planner agent to explore the codebase, ask clarifying "
                    "questions, and produce an implementation plan before any code is written.\n\n"
                    "**Example:** `/plan add JWT authentication to the API`"
                )
            response = await registry._session.orchestrator.handle(
                arg.strip(),
                force_plan=True,
            )
            return response.content

        async def search_handler(arg: str = "", **_: Any) -> str:
            if not arg.strip():
                return (
                    "**Usage:** `/search <query>`\n\n"
                    "Searches the codebase for symbols, functions, and relevant code.\n\n"
                    "Uses hybrid semantic+BM25 (if RAG is enabled) and/or the structural "
                    "symbol index (if `/index` was run).\n\n"
                    "**Examples:**\n"
                    "- `/search ContextDeduplicator` — find by name\n"
                    "- `/search authentication middleware` — semantic search"
                )

            if not registry._session:
                return "Session not initialized."

            query = arg.strip()
            results_parts: list[str] = []

            # 1. Hybrid semantic+BM25 search (requires RAG to be enabled)
            retriever = registry._session.context_retriever
            if retriever:
                try:
                    rag_result = retriever.retrieve(query, max_results=5)
                    if rag_result:
                        results_parts.append(rag_result)
                except Exception:
                    pass

            # 2. Structural symbol index search (requires /index to have been run)
            enricher = getattr(registry._session, "index_enricher", None)
            if enricher and enricher.is_indexed():
                try:
                    db = enricher._db
                    symbols = db.query_symbols(name_like=f"%{query}%")
                    if symbols:
                        lines = [f"### Symbol index ({len(symbols)} match{'es' if len(symbols) != 1 else ''})\n"]
                        for sym in symbols[:20]:
                            file_rec = db.get_file_by_id(sym.file_id)
                            file_path = file_rec.path if file_rec else "?"
                            line_info = f"line {sym.line_start}"
                            if sym.line_end and sym.line_end != sym.line_start:
                                line_info += f"–{sym.line_end}"
                            parent = f" in `{sym.parent_name}`" if sym.parent_name else ""
                            lines.append(
                                f"- **{sym.kind}** `{sym.name}`{parent} — `{file_path}` ({line_info})"
                            )
                        if len(symbols) > 20:
                            lines.append(f"\n_...{len(symbols) - 20} more — refine your query_")
                        results_parts.append("\n".join(lines))
                except Exception:
                    pass

            if not results_parts:
                tips: list[str] = []
                if not retriever:
                    tips.append("enable RAG (`rag.enabled: true` in config)")
                if not (enricher and enricher.is_indexed()):
                    tips.append("run `/index` to build the structural index")
                tip = f"\n\n_Tip: {' or '.join(tips)}._" if tips else ""
                return f"No results found for **`{query}`**." + tip

            return f"## Search: `{query}`\n\n" + "\n\n---\n\n".join(results_parts)

        async def commit_handler(arg: str = "", **_: Any) -> str:
            """Generate a commit message from git diff, confirm, and commit."""
            import asyncio
            import subprocess

            if not registry._session:
                return "Session not initialized."

            def _get_diff() -> tuple[str, str]:
                try:
                    r = subprocess.run(
                        ["git", "diff", "--cached"],
                        capture_output=True, text=True, timeout=10,
                    )
                    if r.stdout.strip():
                        return r.stdout.strip(), "staged"
                    r = subprocess.run(
                        ["git", "diff", "HEAD"],
                        capture_output=True, text=True, timeout=10,
                    )
                    if r.stdout.strip():
                        return r.stdout.strip(), "working tree"
                    return "", "none"
                except FileNotFoundError:
                    return "", "error:git not found"
                except Exception as e:
                    return "", f"error:{e}"

            loop = asyncio.get_event_loop()
            diff, source = await loop.run_in_executor(None, _get_diff)

            if source.startswith("error:"):
                return f"Git error: {source[6:]}"
            if not diff:
                return "No changes found. Stage files with `git add` first."

            # Use provided message or generate one with LLM
            if arg.strip():
                commit_msg = arg.strip()
            else:
                diff_excerpt = diff[:4000]
                from lidco.llm.base import Message as LLMMessage
                try:
                    resp = await registry._session.llm.complete(
                        [LLMMessage(role="user", content=(
                            "Write a git commit message for these changes.\n"
                            "Rules: one line, max 72 chars, format '<type>: <description>'\n"
                            "Types: feat, fix, refactor, docs, test, chore, perf\n"
                            f"\n```diff\n{diff_excerpt}\n```\n\n"
                            "Output ONLY the commit message, nothing else."
                        ))],
                        temperature=0.1,
                        max_tokens=80,
                    )
                    commit_msg = (resp.content or "").strip().strip('"').strip("'")
                except Exception as e:
                    return f"Failed to generate commit message: {e}"

            def _confirm_and_commit(msg: str, diff_source: str) -> str:
                from rich.console import Console as _RC
                from rich.panel import Panel as _Panel
                from rich.prompt import Prompt as _Prompt

                c = _RC()
                c.print()
                c.print(_Panel(
                    f"[bold cyan]{msg}[/bold cyan]\n\n[dim]Changes: {diff_source}[/dim]",
                    title="Proposed Commit",
                    border_style="cyan",
                ))
                answer = _Prompt.ask(
                    "Commit? [[green]y[/green]/[yellow]e[/yellow]dit/[red]n[/red]]",
                    default="y",
                )
                if answer.lower() in ("n", "no", "q", "cancel"):
                    return "__CANCEL__"
                if answer.lower() in ("e", "edit"):
                    msg = _Prompt.ask("New message", default=msg)

                # If nothing staged, auto-stage tracked modified files
                staged_check = subprocess.run(
                    ["git", "diff", "--cached", "--quiet"],
                    capture_output=True, timeout=5,
                )
                if staged_check.returncode == 0:
                    subprocess.run(["git", "add", "-u"], timeout=10)

                result = subprocess.run(
                    ["git", "commit", "-m", msg],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode != 0:
                    return f"__ERROR__:{result.stderr.strip()}"
                return f"__OK__:{result.stdout.strip()}"

            outcome = await loop.run_in_executor(
                None, lambda: _confirm_and_commit(commit_msg, source)
            )

            if outcome == "__CANCEL__":
                return "Commit cancelled."
            if outcome.startswith("__ERROR__:"):
                return f"Commit failed:\n\n```\n{outcome[10:]}\n```"
            return f"Committed successfully:\n\n```\n{outcome[6:]}\n```"

        async def health_handler(arg: str = "", **_: Any) -> str:
            """Show project health overview: lint, tests, TODOs, coverage."""
            import asyncio as _asyncio
            import json as _json
            import re as _re
            from pathlib import Path as _Path

            if not registry._session:
                return "Session not initialized."

            project_dir = registry._session.project_dir

            async def _run_cmd(cmd: list[str]) -> tuple[str, int]:
                try:
                    p = await _asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=_asyncio.subprocess.PIPE,
                        stderr=_asyncio.subprocess.PIPE,
                        cwd=str(project_dir),
                    )
                    stdout, _ = await _asyncio.wait_for(p.communicate(), timeout=30)
                    return stdout.decode("utf-8", errors="replace"), p.returncode or 0
                except _asyncio.TimeoutError:
                    return "", -1
                except FileNotFoundError:
                    return "", -2

            (tests_out, _), (lint_out, lint_rc_raw) = await _asyncio.gather(
                _run_cmd(["python", "-m", "pytest", "--collect-only", "-q", "--tb=no"]),
                _run_cmd(["python", "-m", "ruff", "check", ".", "--statistics"]),
            )

            # --- test count ---
            test_count = 0
            m = _re.search(r"(\d+) tests? collected", tests_out)
            if m:
                test_count = int(m.group(1))

            # --- lint count ---
            lint_available = lint_rc_raw != -2
            lint_count = 0
            if lint_available:
                for line in lint_out.splitlines():
                    mm = _re.match(r"\s*(\d+)\s+[A-Z]\d+", line)
                    if mm:
                        lint_count += int(mm.group(1))

            # --- TODOs/FIXMEs ---
            src_dir = project_dir / "src"
            search_root = src_dir if src_dir.exists() else project_dir
            py_files = list(search_root.rglob("*.py"))
            _todo_pat = _re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")
            todo_count = 0
            for pyf in py_files:
                try:
                    todo_count += len(_todo_pat.findall(pyf.read_text(encoding="utf-8", errors="ignore")))
                except OSError:
                    pass

            # --- coverage from .lidco/coverage.json ---
            coverage_pct: str | None = None
            for cov_path in [
                project_dir / ".lidco" / "coverage.json",
                project_dir / "coverage.json",
            ]:
                if cov_path.exists():
                    try:
                        data = _json.loads(cov_path.read_text(encoding="utf-8"))
                        pct = data.get("totals", {}).get("percent_covered")
                        if pct is not None:
                            coverage_pct = f"{pct:.1f}%"
                    except Exception:
                        pass
                    break

            # --- file counts ---
            test_files = list(project_dir.rglob("test_*.py")) + list(project_dir.rglob("*_test.py"))

            # --- render ---
            lines = ["## Project Health\n", "**Code**"]
            lines.append(f"- Source files: {len(py_files)}")
            lines.append(f"- TODOs / FIXMEs / HACKs: {todo_count}")
            if lint_available:
                flag = " ✓" if lint_count == 0 else ""
                lines.append(f"- Lint issues (ruff): {lint_count}{flag}")
            else:
                lines.append("- Lint: ruff not available")

            lines.append("\n**Tests**")
            lines.append(f"- Test files: {len(test_files)}")
            if test_count:
                lines.append(f"- Tests collected: {test_count}")
            if coverage_pct:
                lines.append(f"- Coverage: {coverage_pct}")
            elif not test_count:
                lines.append("- Run `pytest --cov` to generate coverage data")

            return "\n".join(lines)

        async def todos_handler(arg: str = "", **_: Any) -> str:
            """Find TODO/FIXME/HACK/XXX comments across the codebase."""
            import re as _re
            from pathlib import Path as _Path

            if not registry._session:
                return "Session not initialized."

            project_dir = registry._session.project_dir
            tag_filter = arg.strip().upper() if arg.strip() else None

            valid_tags = {"TODO", "FIXME", "HACK", "XXX"}
            if tag_filter and tag_filter not in valid_tags:
                return (
                    f"Unknown tag `{tag_filter}`. "
                    f"Valid: {', '.join(sorted(valid_tags))}.\n\n"
                    "Usage: `/todos [todo|fixme|hack|xxx]`"
                )

            src_dir = project_dir / "src"
            search_root = src_dir if src_dir.exists() else project_dir
            _pat = _re.compile(r"#\s*(TODO|FIXME|HACK|XXX)[:\s]*(.*)", _re.IGNORECASE)

            entries: list[tuple[str, int, str, str]] = []  # (file, line, tag, comment)
            for pyf in sorted(search_root.rglob("*.py")):
                try:
                    for lineno, line in enumerate(
                        pyf.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
                    ):
                        m = _pat.search(line)
                        if m:
                            tag = m.group(1).upper()
                            comment = m.group(2).strip()[:80]
                            if tag_filter is None or tag == tag_filter:
                                rel = str(pyf.relative_to(project_dir))
                                entries.append((rel, lineno, tag, comment))
                except OSError:
                    pass

            if not entries:
                what = f" matching `{tag_filter}`" if tag_filter else ""
                return f"No TODO comments found{what}."

            limit = 50
            truncated = len(entries) > limit
            display = entries[:limit]

            lines = [f"**{len(entries)} TODO comment{'s' if len(entries) != 1 else ''}**\n"]
            for path, lineno, tag, comment in display:
                lines.append(f"`{path}:{lineno}` **[{tag}]** {comment}")

            if truncated:
                lines.append(f"\n_...{len(entries) - limit} more — filter with `/todos fixme` etc._")

            return "\n".join(lines)

        async def snippet_handler(arg: str = "", **_: Any) -> str:
            """Manage reusable code snippets."""
            if not registry._session:
                return "Session not initialized."

            store = registry._session.snippets
            arg = arg.strip()

            USAGE = (
                "**Snippet commands:**\n\n"
                "- `/snippet list [tag]` — list all snippets (optionally filtered by tag)\n"
                "- `/snippet add name [lang]: code` — save a snippet\n"
                "- `/snippet get name` — display a snippet\n"
                "- `/snippet delete name` — remove a snippet\n"
                "- `/snippet search query` — search snippets by name, content, or tag"
            )

            if not arg or arg == "help":
                return USAGE

            # /snippet list [tag]
            if arg.startswith("list"):
                tag = arg[4:].strip() or None
                entries = store.list_all(tag=tag)
                if not entries:
                    what = f" tagged `{tag}`" if tag else ""
                    return f"No snippets found{what}. Use `/snippet add name: code` to save one."
                lines = [f"**{len(entries)} snippet{'s' if len(entries) != 1 else ''}:**\n"]
                for e in entries:
                    lang_badge = f" `{e.language}`" if e.language else ""
                    tags_badge = f" [{', '.join(e.tags)}]" if e.tags else ""
                    lines.append(f"- **{e.key}**{lang_badge}{tags_badge}")
                return "\n".join(lines)

            # /snippet get name
            if arg.startswith("get "):
                key = arg[4:].strip()
                entry = store.get(key)
                if not entry:
                    return f"Snippet `{key}` not found."
                lang = entry.language or ""
                return f"**{entry.key}**\n\n```{lang}\n{entry.content}\n```"

            # /snippet delete name
            if arg.startswith("delete "):
                key = arg[7:].strip()
                if store.delete(key):
                    return f"Deleted snippet `{key}`."
                return f"Snippet `{key}` not found."

            # /snippet search query
            if arg.startswith("search "):
                query = arg[7:].strip()
                if not query:
                    return "Usage: `/snippet search <query>`"
                results = store.search(query)
                if not results:
                    return f"No snippets matching `{query}`."
                lines = [f"**{len(results)} match{'es' if len(results) != 1 else ''}:**\n"]
                for e in results:
                    preview = e.content[:60].replace("\n", "↵")
                    lines.append(f"- **{e.key}**: `{preview}`")
                return "\n".join(lines)

            # /snippet add name [lang]: code
            if arg.startswith("add "):
                rest = arg[4:].strip()
                if ":" not in rest:
                    return "Usage: `/snippet add name [language]: code`"
                name_part, content = rest.split(":", 1)
                content = content.strip()
                if not content:
                    return "Snippet content cannot be empty."
                # Parse optional language: "my_snippet python"
                name_tokens = name_part.strip().split()
                key = name_tokens[0]
                language = name_tokens[1] if len(name_tokens) > 1 else ""
                if not key:
                    return "Snippet name cannot be empty."
                store.add(key, content, language=language)
                lang_note = f" ({language})" if language else ""
                return f"Saved snippet **{key}**{lang_note} ({len(content)} chars)."

            return f"Unknown sub-command. {USAGE}"

        async def run_handler(arg: str = "", **_: Any) -> str:
            """Run a shell command inline and show output."""
            import asyncio as _asyncio
            import time as _time

            if not arg.strip():
                return (
                    "**Usage:** `/run <command>`\n\n"
                    "Runs a shell command and shows the output.\n\n"
                    "**Example:** `/run pytest tests/unit/ -q`"
                )

            if not registry._session:
                return "Session not initialized."

            project_dir = registry._session.project_dir
            start = _time.monotonic()

            try:
                process = await _asyncio.create_subprocess_shell(
                    arg,
                    stdout=_asyncio.subprocess.PIPE,
                    stderr=_asyncio.subprocess.STDOUT,
                    cwd=str(project_dir),
                )
                stdout, _ = await _asyncio.wait_for(process.communicate(), timeout=120)
            except _asyncio.TimeoutError:
                return "Command timed out after 120s."
            except FileNotFoundError as e:
                return f"Command not found: {e}"

            elapsed = _time.monotonic() - start
            output = stdout.decode("utf-8", errors="replace")

            # Limit to 200 lines
            output_lines = output.splitlines()
            truncated = len(output_lines) > 200
            display = "\n".join(output_lines[:200])
            if truncated:
                display += f"\n... ({len(output_lines) - 200} more lines)"

            rc = process.returncode or 0
            status = "✓" if rc == 0 else f"✗ exit {rc}"
            header = f"`$ {arg}`  [{status}, {elapsed:.1f}s]\n"
            return f"{header}\n```\n{display}\n```" if display.strip() else f"{header}\n_(no output)_"

        async def debug_handler(arg: str = "", **_: Any) -> str:
            """Toggle debug mode (shows full tracebacks inline on tool failures)."""
            if not registry._session:
                return "Session not initialized."

            session = registry._session
            arg = arg.strip().lower()

            if arg == "analyze":
                error_ctx = session._error_history.to_context_str(n=10, extended=True)
                if not error_ctx:
                    return "No errors to analyze."
                response = await session.orchestrator.handle(
                    f"Analyze these recent errors and suggest fixes:\n\n{error_ctx}",
                    agent_name="debugger",
                )
                return response.content

            if arg in ("on", "1", "true", "yes"):
                session.debug_mode = True
                if hasattr(session.orchestrator, "set_debug_mode"):
                    session.orchestrator.set_debug_mode(True)
                return (
                    "**Debug mode enabled.**\n\n"
                    "Full tracebacks will be rendered inline when tools fail.\n"
                    "Planning agents will receive recent error context.\n"
                    "Use `/debug off` to disable."
                )
            if arg in ("off", "0", "false", "no"):
                session.debug_mode = False
                if hasattr(session.orchestrator, "set_debug_mode"):
                    session.orchestrator.set_debug_mode(False)
                return "**Debug mode disabled.**"
            if not arg:
                state = "**enabled**" if session.debug_mode else "**disabled**"
                return (
                    f"Debug mode is currently {state}.\n\n"
                    "Usage: `/debug on|off|analyze`"
                )
            return (
                f"Unknown argument `{arg}`.\n\n"
                "Usage: `/debug on|off|analyze`"
            )

        # Quick fix hints keyed on substrings that appear in error messages.
        # Applied by errors_handler to populate the "Hint" column.
        _ERROR_TAXONOMY_HINTS: dict[str, str] = {
            "'NoneType' object has no attribute": "Add None guard",
            "object has no attribute": "Check type / API change",
            "takes": "Check call signature",
            "positional argument": "Check call signature",
            "unsupported operand type": "Trace value origin",
            "ImportError": "Check pyproject.toml",
            "ModuleNotFoundError": "Check dep installed",
            "KeyError": "Use .get() or verify key",
            "FileNotFoundError": "Check path / cwd",
            "AssertionError": "Read test + impl together",
            "SyntaxError": "Check syntax at line",
            "IndentationError": "Fix indentation",
            "RecursionError": "Find missing base case",
            "coroutine was never awaited": "Add missing await",
            "Permission denied": "Check file permissions",
            "Connection refused": "Check service is running",
            "Timeout": "Increase timeout",
        }

        def _get_error_hint(message: str) -> str:
            """Return the first matching taxonomy hint for *message*, or ''."""
            msg_lower = message.lower()
            for pattern, hint in _ERROR_TAXONOMY_HINTS.items():
                if pattern.lower() in msg_lower:
                    return hint
            return ""

        async def errors_handler(arg: str = "", **_: Any) -> str:
            """View recent tool error history."""
            from io import StringIO
            from rich.console import Console as _RConsole
            from rich.table import Table

            if not registry._session:
                return "Session not initialized."

            # Parse optional N
            try:
                n = max(1, min(50, int(arg.strip()))) if arg.strip() else 5
            except ValueError:
                return f"Invalid argument `{arg}`. Usage: `/errors [N]`"

            history = registry._session._error_history
            records = history.get_recent(n)

            if not records:
                return "No errors recorded in this session."

            table = Table(
                title=f"Recent Errors (last {len(records)})",
                show_header=True,
                header_style="bold red",
            )
            table.add_column("Time", style="dim", width=8)
            table.add_column("Tool", style="cyan")
            table.add_column("Agent", style="blue")
            table.add_column("Type", style="yellow")
            table.add_column("×", style="bold magenta", width=4)
            table.add_column("Message", no_wrap=False)
            table.add_column("Hint", style="green", width=22)

            latest_tb: str | None = None
            for rec in records:
                ts = rec.timestamp.strftime("%H:%M:%S")
                msg = rec.message[:70] + "..." if len(rec.message) > 70 else rec.message
                repeat = str(rec.occurrence_count) if rec.occurrence_count > 1 else ""
                hint = _get_error_hint(rec.message)
                table.add_row(
                    ts, rec.tool_name, rec.agent_name, rec.error_type, repeat, msg, hint
                )
                if rec.traceback_str:
                    latest_tb = rec.traceback_str

            buf = StringIO()
            tmp = _RConsole(file=buf, force_terminal=False, width=120)
            tmp.print(table)
            table_str = f"```\n{buf.getvalue().strip()}\n```"

            if latest_tb:
                tb_lines = latest_tb.strip().splitlines()
                shown = tb_lines[-30:]
                tb_preview = "\n".join(shown)
                if len(tb_lines) > 30:
                    tb_preview = f"[... {len(tb_lines) - 30} lines omitted ...]\n" + tb_preview
                tb_cap = tb_preview[:1500]
                table_str += (
                    f"\n\n**Latest traceback:**\n```python\n{tb_cap}\n```"
                )

            return table_str

        async def changelog_handler(arg: str = "", **_: Any) -> str:
            """Generate a CHANGELOG from git history."""
            import asyncio as _asyncio
            import subprocess as _subprocess

            if not registry._session:
                return "Session not initialized."

            project_dir = registry._session.project_dir
            args_parts = arg.strip().split()
            save_flag = "--save" in args_parts
            refs = [p for p in args_parts if not p.startswith("--")]

            def _git(*cmd: str) -> str:
                try:
                    r = _subprocess.run(
                        ["git", *cmd],
                        capture_output=True, text=True, timeout=15, cwd=str(project_dir),
                    )
                    return r.stdout.strip()
                except Exception:
                    return ""

            # Determine range
            if len(refs) >= 2:
                from_ref, to_ref = refs[0], refs[1]
            elif len(refs) == 1:
                from_ref, to_ref = refs[0], "HEAD"
            else:
                # Try last tag → HEAD
                last_tag = _git("describe", "--tags", "--abbrev=0")
                from_ref = last_tag if last_tag else ""
                to_ref = "HEAD"

            range_str = f"{from_ref}..{to_ref}" if from_ref else to_ref
            commits_raw = _git(
                "log", "--oneline", "--no-merges", range_str
            )
            if not commits_raw:
                return f"No commits found in range `{range_str}`."

            commit_lines = commits_raw.splitlines()[:200]
            commits_text = "\n".join(commit_lines)

            from_label = from_ref or "beginning"
            prompt = (
                f"Generate a CHANGELOG.md section from these git commits ({from_label}..{to_ref}).\n\n"
                "Group into sections: ### Features, ### Bug Fixes, ### Refactoring, ### Docs, ### Other.\n"
                "Format each item as `- <description>` (no SHA). Skip trivial commits.\n"
                "Output ONLY the markdown, starting with `## [Unreleased]`.\n\n"
                f"```\n{commits_text}\n```"
            )

            from lidco.llm.base import Message as _Msg
            try:
                resp = await registry._session.llm.complete(
                    [_Msg(role="user", content=prompt)],
                    temperature=0.2,
                    max_tokens=1500,
                )
                changelog = (resp.content or "").strip()
            except Exception as e:
                return f"LLM error: {e}"

            if save_flag:
                out_path = project_dir / "CHANGELOG.md"
                existing = out_path.read_text(encoding="utf-8") if out_path.exists() else ""
                new_content = changelog + ("\n\n" + existing if existing else "")
                out_path.write_text(new_content, encoding="utf-8")
                return f"Saved to `CHANGELOG.md`.\n\n{changelog}"

            return changelog

        self.register(SlashCommand("help", "Show available commands", help_handler))
        self.register(SlashCommand("debug", "Toggle debug mode (show/hide full tracebacks)", debug_handler))
        self.register(SlashCommand("errors", "View recent error history [N=5]", errors_handler))
        self.register(SlashCommand("health", "Project health: lint, tests, TODOs, coverage", health_handler))
        self.register(SlashCommand("todos", "Find TODO/FIXME/HACK/XXX comments", todos_handler))
        async def arch_handler(arg: str = "", **_: Any) -> str:
            """Render ASCII architecture diagram from dependency index."""
            import asyncio as _asyncio

            if not registry._session:
                return "Session not initialized."

            parts = arg.strip().split()
            root_path = parts[0] if parts else ""
            direction = "both"
            max_depth = 2
            for p in parts[1:]:
                if p in ("dependencies", "dependents", "both"):
                    direction = p
                elif p.isdigit():
                    max_depth = int(p)

            tool = registry._session.tool_registry.get("arch_diagram")
            if not tool:
                return "arch_diagram tool not registered."

            result = await tool.execute(
                root_path=root_path,
                direction=direction,
                max_depth=max_depth,
            )
            if not result.success:
                return f"Error: {result.error}"
            return result.output

        async def pr_handler(arg: str = "", **_: Any) -> str:
            """Load or clear an active GitHub PR context via the gh CLI."""
            if not registry._session:
                return "Session not initialized."

            arg = arg.strip()

            # /pr close | /pr clear
            if arg.lower() in ("close", "clear"):
                registry._session.active_pr_context = None
                return "PR context cleared. Agents will no longer receive PR information."

            # /pr (no arg) — show current state or usage
            if not arg:
                current = getattr(registry._session, "active_pr_context", None)
                if current:
                    preview = current[:400] + "\n..." if len(current) > 400 else current
                    return (
                        "**Active PR context (preview):**\n\n"
                        f"{preview}\n\n"
                        "_Use `/pr close` to clear._"
                    )
                return (
                    "**Usage:**\n\n"
                    "- `/pr <number>` — load PR context into agents (requires `gh auth login`)\n"
                    "- `/pr close` — clear active PR context\n\n"
                    "**Example:** `/pr 123`"
                )

            # /pr <number>
            from lidco.tools.gh_pr import GHPRTool
            tool = GHPRTool()
            result = await tool.execute(number=arg)

            if not result.success:
                return f"Failed to fetch PR #{arg}: {result.error or 'unknown error'}"

            registry._session.active_pr_context = result.output

            title = result.metadata.get("title", "")
            state = result.metadata.get("state", "")
            files_count = result.metadata.get("files_count", 0)
            number = result.metadata.get("number", arg)
            additions = result.metadata.get("additions", 0)
            deletions = result.metadata.get("deletions", 0)

            return (
                f"Loaded PR #{number}: **{title}**\n\n"
                f"State: {state}  |  {files_count} changed file{'s' if files_count != 1 else ''}  |  "
                f"+{additions} −{deletions}\n\n"
                "_PR context will be injected into all agent turns. Use `/pr close` to clear._"
            )

        self.register(SlashCommand("snippet", "Save and recall reusable code snippets", snippet_handler))
        self.register(SlashCommand("run", "Run a shell command inline", run_handler))
        self.register(SlashCommand("changelog", "Generate CHANGELOG from git history", changelog_handler))
        self.register(SlashCommand("arch", "Show architecture dependency diagram", arch_handler))
        self.register(SlashCommand("search", "Search the codebase (symbols + semantic)", search_handler))
        self.register(SlashCommand("commit", "Generate a commit message and commit", commit_handler))
        self.register(SlashCommand("plan", "Plan a task before implementation", plan_handler))
        self.register(SlashCommand("model", "Switch or show current LLM model", model_handler))
        self.register(SlashCommand("agents", "List available agents", agents_handler))
        self.register(SlashCommand("memory", "Manage persistent memory", memory_handler))
        self.register(SlashCommand("context", "Show current project context", context_handler))
        self.register(SlashCommand("index", "Build/update the structural project index", index_handler))
        self.register(SlashCommand("index-status", "Show current index statistics", index_status_handler))
        self.register(SlashCommand("init", "Initialize LIDCO.md rules file", init_handler))
        self.register(SlashCommand("rules", "Manage project rules", rules_handler))
        self.register(SlashCommand("decisions", "Manage clarification decisions", decisions_handler))
        self.register(SlashCommand("export", "Export session to JSON (default) or Markdown (--md)", export_handler))
        self.register(SlashCommand("import", "Restore session from a JSON export file", import_handler))
        self.register(SlashCommand("pr", "Load GitHub PR context into agents via gh CLI", pr_handler))
        self.register(SlashCommand("clear", "Clear conversation history", clear_handler))
        self.register(SlashCommand("config", "Show or set runtime configuration", config_handler))
        self.register(SlashCommand("exit", "Exit LIDCO", exit_handler))
