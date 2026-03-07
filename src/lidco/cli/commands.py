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
        self.last_message: str = ""           # set by app.py after each user turn
        self.locked_agent: str | None = None  # Task 152: /lock <agent>
        self.session_note: str = ""           # Task 167: /note sticky context
        self._aliases: dict[str, str] = {}    # Task 169: /alias
        self._edited_files: list[str] = []    # Task 171: /recent tracking
        self.focus_file: str = ""             # Task 172: /focus sticky file
        self._pins: list[str] = []            # Task 173: /pin persistent context
        self._vars: dict[str, str] = {}       # Task 174: /vars template substitution
        self._turn_times: list[float] = []    # Task 175: /timing per-turn elapsed
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
        registry = self

        # Task 156: categorised /help with examples
        _HELP_CATEGORIES: list[tuple[str, list[tuple[str, str]]]] = [
            ("Агенты", [
                ("/agents", "список доступных агентов"),
                ("@<агент> <сообщение>", "обратиться напрямую к агенту"),
                ("/as <агент> <сообщение>", "одноразовый запрос к агенту"),
                ("/lock <агент>", "закрепить агента на всю сессию"),
                ("/unlock", "снять закрепление агента"),
            ]),
            ("Сессия", [
                ("/status", "дашборд здоровья сессии"),
                ("/retry [сообщение]", "повторить последний запрос"),
                ("/undo [--force]", "откатить изменения файлов через git"),
                ("/clear", "очистить историю диалога"),
                ("/exit", "выйти из LIDCO"),
            ]),
            ("Код и анализ", [
                ("/search <запрос>", "поиск символов и семантика"),
                ("/lint [путь]", "ruff + mypy статический анализ"),
                ("/health", "здоровье проекта: тесты, покрытие, TODO"),
                ("/todos", "найти TODO/FIXME/HACK комментарии"),
                ("/arch", "диаграмма зависимостей архитектуры"),
                ("/plan <задача>", "спланировать перед реализацией"),
                ("/commit", "сгенерировать и создать коммит"),
                ("/run <команда>", "выполнить shell-команду"),
            ]),
            ("Отладка", [
                ("/debug on|off", "включить/выключить режим отладки"),
                ("/debug kb|stats|preset", "база знаний, статистика, пресеты"),
                ("/errors [N]", "история ошибок (по умолчанию 5)"),
                ("/errors --tree", "дерево причинно-следственных связей"),
                ("/errors --timeline", "временная шкала ошибок"),
            ]),
            ("Модель", [
                ("/model", "показать текущую модель"),
                ("/model <название>", "сменить модель (напр. openai/gpt-4o)"),
                ("/config", "показать/изменить конфигурацию"),
            ]),
            ("Память и контекст", [
                ("/memory", "управление постоянной памятью"),
                ("/context", "текущий контекст проекта"),
                ("/index", "построить/обновить индекс проекта"),
                ("/rules", "управление правилами проекта"),
                ("/init", "создать LIDCO.md файл правил"),
            ]),
            ("Импорт / Экспорт", [
                ("/export", "экспорт сессии в JSON"),
                ("/export --md", "экспорт сессии в Markdown"),
                ("/import <файл>", "восстановить сессию из файла"),
                ("/pr <номер>", "загрузить контекст GitHub PR"),
                ("/changelog", "сгенерировать CHANGELOG из git"),
            ]),
            ("Веб", [
                ("/websearch <запрос>", "поиск через DuckDuckGo"),
                ("/webfetch <url>", "загрузить веб-страницу"),
            ]),
        ]

        _HELP_EXAMPLES: dict[str, list[str]] = {
            "as":       ["/as coder исправь баг в auth.py", "/as debugger проанализируй traceback"],
            "lock":     ["/lock coder", "/lock off"],
            "debug":    ["/debug on", "/debug kb", "/debug preset thorough"],
            "errors":   ["/errors", "/errors 10", "/errors --tree"],
            "search":   ["/search UserRepository", "/search авторизация"],
            "lint":     ["/lint", "/lint src/lidco/core/"],
            "plan":     ["/plan добавить JWT аутентификацию"],
            "model":    ["/model openai/gpt-4o", "/model anthropic/claude-opus-4-5"],
            "export":   ["/export", "/export --md"],
            "websearch":["/websearch python asyncio best practices"],
            "commit":   ["/commit"],
            "run":      ["/run pytest -q", "/run git status"],
            "undo":     ["/undo", "/undo --force"],
            "retry":    ["/retry", "/retry с более подробным объяснением"],
        }

        async def help_handler(arg: str = "", **_: Any) -> str:
            # /help <command> — detailed help for one command
            if arg.strip():
                cmd_name = arg.strip().lstrip("/")
                cmd = registry.get(cmd_name)
                if cmd is None:
                    return f"Команда `/{cmd_name}` не найдена. Введите `/help` для списка."
                lines = [f"## `/{cmd.name}`", "", cmd.description, ""]
                examples = _HELP_EXAMPLES.get(cmd_name)
                if examples:
                    lines.append("**Примеры:**")
                    for ex in examples:
                        lines.append(f"  `{ex}`")
                return "\n".join(lines)

            # /help — full categorised listing
            lines = ["## Справка LIDCO", ""]
            for category, entries in _HELP_CATEGORIES:
                lines.append(f"**{category}**")
                for cmd_str, desc in entries:
                    lines.append(f"  `{cmd_str}` — {desc}")
                lines.append("")
            lines.append("**/help `<команда>`** — подробная справка и примеры для команды.")
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
                except Exception as e:
                    logger.debug("RAG search failed: %s", e)

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
                except Exception as e:
                    logger.debug("Symbol index search failed: %s", e)

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
                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                    )
                    if r.stdout.strip():
                        return r.stdout.strip(), "staged"
                    r = subprocess.run(
                        ["git", "diff", "HEAD"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
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
                    add_result = subprocess.run(
                        ["git", "add", "-u"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
                    )
                    if add_result.returncode != 0:
                        return f"__ERROR__:Failed to stage changes: {add_result.stderr.strip()}"

                result = subprocess.run(
                    ["git", "commit", "-m", msg],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
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

            # /debug kb [query] — search fix memory
            if arg.startswith("kb"):
                query = arg[2:].strip()
                try:
                    fix_memory = getattr(session, "_fix_memory", None)
                    if not fix_memory:
                        return "Fix memory not available in this session."
                    results = fix_memory.find_similar("", "", query) if query else []
                    if not results:
                        if query:
                            return f"No past fixes found for: `{query}`"
                        return "Fix memory is empty. Fixes are recorded after successful debug sessions."
                    lines = [f"**Found {len(results)} similar past fix(es):**\n"]
                    for i, fp in enumerate(results, 1):
                        from lidco.core.fix_memory import confidence_label
                        label = confidence_label(fp.confidence)
                        lines.append(
                            f"{i}. [{label} confidence] `{fp.file_module}:{fp.function_hint}` → {fp.error_type}\n"
                            f"   Fix: {fp.fix_description}\n"
                            f"   Changes: {fp.diff_summary}\n"
                        )
                    return "\n".join(lines)
                except Exception as _e:
                    return f"Fix memory search failed: {_e}"

            # /debug stats — debugger metrics dashboard
            if arg == "stats":
                try:
                    fix_memory = getattr(session, "_fix_memory", None)
                    ledger = getattr(session, "_error_ledger", None)
                    lines = ["## Debug Statistics\n"]
                    if fix_memory:
                        all_fixes = fix_memory.find_similar("", "", "") if hasattr(fix_memory, "find_similar") else []
                        lines.append(f"Patterns in fix memory: {len(all_fixes)}")
                    if ledger:
                        recurring = ledger.get_recurring(min_sessions=2)
                        frequent = ledger.get_frequent(min_occurrences=5)
                        lines.append(f"Recurring errors (2+ sessions): {len(recurring)}")
                        lines.append(f"Frequent errors (5+ occurrences): {len(frequent)}")
                        if recurring:
                            lines.append("\n**Most recurring issues:**")
                            for r in recurring[:5]:
                                msg = (r.get("sample_message") or "")[:60]
                                lines.append(
                                    f"  - {msg!r} × {r['total_occurrences']} "
                                    f"in {r['sessions_count']} sessions"
                                )
                    error_history = session._error_history
                    recent = error_history.get_recent(50)
                    if recent:
                        from collections import Counter
                        type_counts = Counter(r.error_type for r in recent)
                        lines.append(f"\nErrors this session: {len(recent)}")
                        lines.append("**Error types:**")
                        for etype, count in type_counts.most_common(5):
                            lines.append(f"  {etype}: {count}")
                    return "\n".join(lines)
                except Exception as _e:
                    return f"Stats failed: {_e}"

            # /debug preset fast|balanced|thorough|silent
            if arg.startswith("preset"):
                preset_name = arg[6:].strip()
                _VALID_PRESETS = {"fast", "balanced", "thorough", "silent"}
                if not preset_name:
                    orch = session.orchestrator
                    current = getattr(orch, "_debug_preset", "balanced")
                    return (
                        f"Current debug preset: **{current}**\n\n"
                        "Available presets: `fast | balanced | thorough | silent`\n"
                        "Usage: `/debug preset <name>`"
                    )
                if preset_name not in _VALID_PRESETS:
                    return (
                        f"Unknown preset `{preset_name}`.\n"
                        "Available: `fast | balanced | thorough | silent`"
                    )
                if hasattr(session.orchestrator, "set_debug_preset"):
                    session.orchestrator.set_debug_preset(preset_name)
                    session.config = session.config.model_copy(
                        update={"agents": session.config.agents.model_copy(
                            update={"debug_preset": preset_name}
                        )}
                    )
                return f"Debug preset set to **{preset_name}**."

            # /debug autopilot [test_path] — run test autopilot
            if arg.startswith("autopilot"):
                test_path = arg[9:].strip()
                tool = session.tool_registry.get("run_debug_cycle")
                if not tool:
                    return "Test autopilot tool not registered. Ensure TestAutopilotTool is in the registry."
                result = await tool.execute(test_path=test_path, max_rounds=3)
                return result.output

            if not arg:
                orch = session.orchestrator
                preset = getattr(orch, "_debug_preset", "balanced")
                state = "**enabled**" if session.debug_mode else "**disabled**"
                hypothesis = getattr(orch, "_debug_hypothesis_enabled", True)
                fast_path = getattr(orch, "_debug_fast_path_enabled", True)
                return (
                    f"Debug mode is currently {state}.\n\n"
                    f"Preset: `{preset}` | Hypothesis: {'✓' if hypothesis else '✗'} | "
                    f"Fast-path: {'✓' if fast_path else '✗'}\n\n"
                    "Usage: `/debug on|off|analyze|kb [query]|stats|preset <name>|autopilot [path]`"
                )
            return (
                f"Unknown argument `{arg}`.\n\n"
                "Usage: `/debug on|off|analyze|kb [query]|stats|preset <name>|autopilot [path]`"
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

            session = registry._session

            # /errors --tree — show causal chain
            if arg.strip() == "--tree":
                history = session._error_history
                chain_str = history.to_causal_chain_str()
                if not chain_str:
                    return "No errors recorded or no causal relationships found."
                return f"```\n{chain_str}\n```"

            # /errors --timeline — show ASCII error timeline
            if arg.strip() == "--timeline":
                from lidco.core.error_timeline import build_timeline
                history = session._error_history
                records = history.get_recent(50)
                timeline = build_timeline(records, project_dir=session.project_dir)
                return f"```\n{timeline}\n```"

            # /errors --history — show cross-session recurring errors from ledger
            if arg.strip() == "--history":
                ledger = getattr(session, "_error_ledger", None)
                if not ledger:
                    return "Error ledger not available."
                recurring = ledger.get_recurring(min_sessions=1)
                if not recurring:
                    return "No cross-session error history found."
                lines = ["## Cross-Session Error History\n"]
                for r in recurring[:20]:
                    status = "✓ FIXED" if r.get("fix_applied") else "⚠ unfixed"
                    msg = (r.get("sample_message") or "")[:80]
                    lines.append(
                        f"- [{status}] `{r['error_hash']}` × {r['total_occurrences']} "
                        f"in {r['sessions_count']} session(s): {msg}"
                    )
                    if r.get("fix_description"):
                        lines.append(f"  Fix: {r['fix_description']}")
                return "\n".join(lines)

            # Parse optional N
            try:
                n = max(1, min(50, int(arg.strip()))) if arg.strip() else 5
            except ValueError:
                return f"Invalid argument `{arg}`. Usage: `/errors [N|--tree|--timeline|--history]`"

            history = session._error_history
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
                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15, cwd=str(project_dir),
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

            metadata = result.metadata or {}
            title = metadata.get("title", "")
            state = metadata.get("state", "")
            files_count = metadata.get("files_count", 0)
            number = metadata.get("number", arg)
            additions = metadata.get("additions", 0)
            deletions = metadata.get("deletions", 0)

            return (
                f"Loaded PR #{number}: **{title}**\n\n"
                f"State: {state}  |  {files_count} changed file{'s' if files_count != 1 else ''}  |  "
                f"+{additions} −{deletions}\n\n"
                "_PR context will be injected into all agent turns. Use `/pr close` to clear._"
            )

        async def lint_handler(arg: str = "", **_: Any) -> str:
            """Run ruff + mypy static analysis on Python files."""
            if not registry._session:
                return "Session not initialized."
            tool = registry._session.tool_registry.get("run_static_analysis")
            if not tool:
                return "Static analyzer tool not available."
            paths = [arg.strip()] if arg.strip() else []
            result = await tool.execute(paths=paths, checks=["ruff", "mypy"])
            return result.output

        self.register(SlashCommand("lint", "Run ruff + mypy static analysis [path]", lint_handler))
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

        # ── Q31: /status, /retry, /undo ─────────────────────────────────────

        async def status_handler(**_: Any) -> str:
            """Show current session health dashboard."""
            if not registry._session:
                return "Session not initialized."
            sess = registry._session
            tb = getattr(sess, "token_budget", None)
            total_tok = getattr(tb, "_total_tokens", 0) if tb else 0
            prompt_tok = getattr(tb, "_total_prompt_tokens", 0) if tb else 0
            completion_tok = getattr(tb, "_total_completion_tokens", 0) if tb else 0
            total_cost = getattr(tb, "_total_cost_usd", 0.0) if tb else 0.0
            by_role: dict = getattr(tb, "_by_role", {}) if tb else {}
            session_limit = getattr(tb, "session_limit", 0) if tb else 0

            mem = getattr(sess, "memory", None)
            mem_count = len(mem.list_all()) if mem and hasattr(mem, "list_all") else 0

            tool_reg = getattr(sess, "tool_registry", None)
            tool_count = len(tool_reg.list_tools()) if tool_reg and hasattr(tool_reg, "list_tools") else 0

            cfg = getattr(sess, "config", None)
            model = cfg.llm.default_model if cfg else "?"
            debug_on = getattr(sess, "debug_mode", False)

            def _k(n: int) -> str:
                return f"{n / 1000:.1f}k" if n >= 1000 else str(n)

            lines = [
                f"**Model:**    {model}",
                f"**Debug:**    {'on' if debug_on else 'off'}",
                "",
                f"**Tokens:**   {_k(total_tok)} total  "
                f"({_k(prompt_tok)} in / {_k(completion_tok)} out)",
            ]
            if session_limit > 0:
                pct = int(total_tok / session_limit * 100)
                lines.append(f"**Budget:**   {pct}% of {_k(session_limit)} limit")
            if total_cost > 0:
                cost_fmt = f"${total_cost:.6f}".rstrip("0").rstrip(".")
                lines.append(f"**Cost:**     {cost_fmt}")
            if by_role:
                lines.append("")
                lines.append("**By agent:**")
                for role, toks in sorted(by_role.items(), key=lambda x: -x[1])[:6]:
                    lines.append(f"  · {role}: {_k(toks)}")
            lines += [
                "",
                f"**Memory:**   {mem_count} entries",
                f"**Tools:**    {tool_count} registered",
            ]
            # Task 170: show session state
            hist_len = len(getattr(
                getattr(sess, "orchestrator", None),
                "_conversation_history", []
            ))
            lines.append(f"**History:**  {hist_len} messages")
            if registry.locked_agent:
                lines.append(f"**Locked:**   {registry.locked_agent}")
            if registry.session_note:
                preview = registry.session_note[:60]
                if len(registry.session_note) > 60:
                    preview += "…"
                lines.append(f"**Note:**     {preview}")
            if registry._aliases:
                lines.append(f"**Aliases:**  {', '.join(f'/{k}' for k in sorted(registry._aliases))}")
            if registry._edited_files:
                lines.append(f"**Edited:**   {len(set(registry._edited_files))} файлов")
            if registry.focus_file:
                lines.append(f"**Focus:**    {registry.focus_file}")
            return "\n".join(lines)

        async def retry_handler(arg: str = "", **_: Any) -> str:
            """Resend the last user message (or a new one if arg is given)."""
            msg = arg.strip() or registry.last_message
            if not msg:
                return "Nothing to retry. Send a message first."
            return f"__RETRY__:{msg}"

        async def undo_handler(arg: str = "", **_: Any) -> str:
            """Show or revert recent file changes via git restore."""
            import asyncio
            import subprocess

            force = arg.strip() == "--force"

            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: subprocess.run(
                        ["git", "diff", "--name-only", "HEAD"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5
                    )
                )
                modified = [l for l in result.stdout.splitlines() if l.strip()]

                new_result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: subprocess.run(
                        ["git", "ls-files", "--others", "--exclude-standard"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5
                    )
                )
                untracked = [l for l in new_result.stdout.splitlines() if l.strip()]
            except Exception as e:
                return f"Git error: {e}"

            if not modified and not untracked:
                return "No uncommitted changes found."

            lines = ["**Uncommitted changes:**", ""]
            for f in modified[:15]:
                lines.append(f"  · `{f}` (modified)")
            for f in untracked[:5]:
                lines.append(f"  · `{f}` (new file)")
            if len(modified) > 15 or len(untracked) > 5:
                lines.append(f"  · ... and more")
            lines.append("")

            if not force:
                lines.append(
                    "Run `/undo --force` to restore all tracked modifications to HEAD.\n"
                    "_Newly created files will **not** be deleted automatically._"
                )
                return "\n".join(lines)

            # --force: restore tracked modifications
            if modified:
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: subprocess.run(
                            ["git", "restore"] + modified,
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
                        )
                    )
                    lines.append(f"Restored {len(modified)} file(s) to HEAD.")
                except Exception as e:
                    lines.append(f"Restore error: {e}")
            else:
                lines.append("No tracked modifications to restore.")
            return "\n".join(lines)

        self.register(SlashCommand("status", "Show session health dashboard", status_handler))
        self.register(SlashCommand("retry", "Resend last message [or new message]", retry_handler))
        self.register(SlashCommand("undo", "Show/revert file changes via git restore [--force]", undo_handler))

        # ── Q32: /websearch, /webfetch ────────────────────────────────────────

        async def websearch_handler(arg: str = "", **_: Any) -> str:
            """Search the web via DuckDuckGo and return formatted results."""
            query = arg.strip()
            if not query:
                return (
                    "**Usage:** `/websearch <query>`\n\n"
                    "Searches DuckDuckGo and returns titles, URLs, and snippets.\n\n"
                    "**Example:** `/websearch python asyncio timeout`\n\n"
                    "Use `/webfetch <url>` to fetch the full text of any result URL."
                )

            from lidco.tools.web_search import WebSearchTool
            tool = WebSearchTool()
            result = await tool._run(query=query, max_results=8)

            if not result.success:
                return f"Search failed: {result.error}"

            output = result.output

            # Append /webfetch hint if any URLs were returned
            if "https://" in output or "http://" in output:
                output += (
                    "\n\n---\n"
                    "_Tip: Use `/webfetch <url>` to fetch the full text of any URL above._"
                )

            return output

        async def webfetch_handler(arg: str = "", **_: Any) -> str:
            """Fetch a web page and return its text content."""
            url = arg.strip()
            if not url:
                return (
                    "**Usage:** `/webfetch <url>`\n\n"
                    "Fetches a web page and returns its plain-text content.\n\n"
                    "**Example:** `/webfetch https://docs.python.org/3/library/asyncio.html`"
                )

            from lidco.tools.web_fetch import WebFetchTool
            tool = WebFetchTool()
            result = await tool._run(url=url)

            if not result.success:
                return f"Fetch failed: {result.error}"

            return result.output

        self.register(SlashCommand("websearch", "Search the web via DuckDuckGo", websearch_handler))
        self.register(SlashCommand("webfetch", "Fetch a web page as plain text", webfetch_handler))

        # ── Task 152: agent switching ─────────────────────────────────────────

        async def as_handler(arg: str = "", **_: Any) -> str:
            """/as <agent> <message> — одноразовый запрос к конкретному агенту."""
            parts = arg.strip().split(maxsplit=1)
            if len(parts) < 2:
                agents = (
                    registry._session.agent_registry.list_names()
                    if registry._session
                    else []
                )
                available = ", ".join(f"`{a}`" for a in agents) if agents else "—"
                return (
                    "**Использование:** `/as <агент> <сообщение>`\n\n"
                    f"**Доступные агенты:** {available}\n\n"
                    "**Пример:** `/as coder исправь баг в auth.py`"
                )
            agent_name, message = parts[0], parts[1]
            if registry._session:
                available = registry._session.agent_registry.list_names()
                if agent_name not in available:
                    return (
                        f"Агент **{agent_name}** не найден.\n"
                        f"Доступные: {', '.join(f'`{a}`' for a in available)}"
                    )
            # Reuse the @agent routing in the REPL via the __RETRY__ mechanism
            return f"__RETRY__:@{agent_name} {message}"

        async def lock_handler(arg: str = "", **_: Any) -> str:
            """/lock [<agent>|off] — закрепить агента для всей сессии."""
            arg = arg.strip()

            if not arg:
                if registry.locked_agent:
                    return (
                        f"Агент **{registry.locked_agent}** закреплён.\n"
                        "Используйте `/lock off` или `/unlock` для снятия блокировки."
                    )
                return (
                    "Агент не закреплён — используется авторотация.\n"
                    "**Использование:** `/lock <агент>` или `/lock off`"
                )

            if arg in ("off", "clear", "none", "auto"):
                registry.locked_agent = None
                return "Блокировка агента снята — вернулась авторотация."

            if registry._session:
                available = registry._session.agent_registry.list_names()
                if arg not in available:
                    return (
                        f"Агент **{arg}** не найден.\n"
                        f"Доступные: {', '.join(f'`{a}`' for a in available)}"
                    )
            registry.locked_agent = arg
            return (
                f"Агент **{arg}** закреплён для всей сессии.\n"
                "Каждый запрос теперь идёт к нему. `/unlock` — снять блокировку."
            )

        async def unlock_handler(**_: Any) -> str:
            """/unlock — снять блокировку агента."""
            if registry.locked_agent is None:
                return "Агент не был закреплён."
            prev = registry.locked_agent
            registry.locked_agent = None
            return f"Блокировка агента **{prev}** снята — вернулась авторотация."

        self.register(SlashCommand("as", "Одноразовый запрос к конкретному агенту: /as <агент> <сообщение>", as_handler))
        self.register(SlashCommand("lock", "Закрепить агента для сессии: /lock <агент> | /lock off", lock_handler))
        self.register(SlashCommand("unlock", "Снять блокировку агента", unlock_handler))

        # ── Task 159: /shortcuts ───────────────────────────────────────────────

        async def shortcuts_handler(**_: Any) -> str:
            """/shortcuts — список горячих клавиш."""
            rows = [
                ("Ctrl+L", "/clear — очистить историю (всегда)"),
                ("Ctrl+R", "/retry — повторить последний запрос (если буфер пуст)"),
                ("Ctrl+E", "/export — экспортировать диалог (если буфер пуст)"),
                ("Ctrl+P", "/status — показать дашборд (если буфер пуст)"),
                ("Ctrl+J", "Отправить сообщение (альтернатива Enter)"),
                ("Esc+Enter", "Новая строка (мультилайн режим)"),
            ]
            lines = ["## Горячие клавиши", ""]
            for key, desc in rows:
                lines.append(f"  `{key}` — {desc}")
            lines.append("")
            lines.append("*Подсказка:* начните вводить `/`, затем нажмите Tab для автодополнения команд.")
            return "\n".join(lines)

        self.register(SlashCommand("shortcuts", "Показать горячие клавиши", shortcuts_handler))

        # ── Task 160: /whois <agent> ───────────────────────────────────────────

        async def whois_handler(arg: str = "", **_: Any) -> str:
            """/whois <agent> — подробная карточка агента."""
            agent_name = arg.strip().lstrip("@")
            if not agent_name:
                agents = (
                    registry._session.agent_registry.list_names()
                    if registry._session else []
                )
                available = ", ".join(f"`{a}`" for a in agents) if agents else "—"
                return (
                    "**Использование:** `/whois <агент>`\n\n"
                    f"**Доступные агенты:** {available}\n\n"
                    "**Пример:** `/whois coder`"
                )
            if not registry._session:
                return "Сессия не инициализирована."
            known = registry._session.agent_registry.list_names()
            if agent_name not in known:
                available = ", ".join(f"`{n}`" for n in known)
                return (
                    f"Агент **{agent_name}** не найден.\n\n"
                    f"Доступные: {available}"
                )
            try:
                agent = registry._session.agent_registry.get(agent_name)
            except Exception:
                return f"Ошибка при получении агента **{agent_name}**."
            name = str(agent.name)
            desc = str(agent.description)
            lines = [f"## {name}", "", desc, ""]
            # Show tools if agent exposes them
            try:
                tool_names = list(agent.tools.keys()) if hasattr(agent, "tools") else []
                if tool_names:
                    lines.append("**Инструменты:**")
                    for t in sorted(tool_names):
                        lines.append(f"  · `{t}`")
                    lines.append("")
            except Exception:
                pass
            lines.append(f"*Обратиться: `@{name} <сообщение>` или `/as {name} <сообщение>`*")
            return "\n".join(lines)

        self.register(SlashCommand("whois", "Карточка агента: описание и инструменты", whois_handler))

        # ── Task 161: /compact ─────────────────────────────────────────────────

        _COMPACT_DEFAULT_KEEP = 6  # keep last 6 messages (3 turns) by default

        async def compact_handler(arg: str = "", **_: Any) -> str:
            """/compact [N] — оставить последние N сообщений, остальное удалить."""
            if not registry._session:
                return "Сессия не инициализирована."
            try:
                keep = int(arg.strip()) if arg.strip() else _COMPACT_DEFAULT_KEEP
                if keep < 2:
                    keep = 2
            except ValueError:
                return f"Неверный аргумент: `{arg}`. Использование: `/compact [N]` (N — количество сообщений)."

            orch = registry._session.orchestrator
            history = list(getattr(orch, "_conversation_history", []))
            total = len(history)
            if total <= keep:
                return (
                    f"История уже короткая ({total} сообщений). "
                    f"Нечего сжимать. Минимум для сжатия: {keep + 1}."
                )
            compacted = history[-keep:]
            orch.restore_history(compacted)
            removed = total - keep
            return (
                f"Контекст сжат: удалено **{removed}** сообщений, "
                f"оставлено последних **{keep}** (из {total})."
            )

        self.register(SlashCommand(
            "compact",
            "Сжать историю диалога, оставив последние N сообщений [N=6]",
            compact_handler,
        ))

        # ── Task 164: /history ─────────────────────────────────────────────────

        _HISTORY_DEFAULT_TURNS = 5

        async def history_handler(arg: str = "", **_: Any) -> str:
            """/history [N] — показать последние N ходов диалога."""
            if not registry._session:
                return "Сессия не инициализирована."
            try:
                n = int(arg.strip()) if arg.strip() else _HISTORY_DEFAULT_TURNS
                if n < 1:
                    n = 1
            except ValueError:
                return f"Неверный аргумент: `{arg}`. Использование: `/history [N]`"

            orch = registry._session.orchestrator
            raw = list(getattr(orch, "_conversation_history", []))
            if not raw:
                return "История диалога пуста."

            # Group into user+assistant pairs (turns)
            turns: list[tuple[str, str]] = []
            i = 0
            while i < len(raw):
                msg = raw[i]
                role = msg.get("role", "")
                content = str(msg.get("content", ""))
                if role == "user":
                    assistant_content = ""
                    if i + 1 < len(raw) and raw[i + 1].get("role") == "assistant":
                        assistant_content = str(raw[i + 1].get("content", ""))
                        i += 1
                    turns.append((content, assistant_content))
                i += 1

            recent = turns[-n:]
            if not recent:
                return "История диалога пуста."

            lines = [f"## История диалога (последние {len(recent)} из {len(turns)} ходов)", ""]
            for idx, (user_msg, asst_msg) in enumerate(recent, start=len(turns) - len(recent) + 1):
                user_preview = user_msg[:120].replace("\n", " ")
                if len(user_msg) > 120:
                    user_preview += "…"
                lines.append(f"**Ход {idx}** — Вы: {user_preview}")
                if asst_msg:
                    asst_preview = asst_msg[:120].replace("\n", " ")
                    if len(asst_msg) > 120:
                        asst_preview += "…"
                    lines.append(f"  → Ответ: {asst_preview}")
                lines.append("")
            lines.append(f"*Всего сообщений в истории: {len(raw)}. `/compact` — сжать.*")
            return "\n".join(lines)

        self.register(SlashCommand("history", "Показать последние N ходов диалога [N=5]", history_handler))

        # ── Task 165: /budget ──────────────────────────────────────────────────

        async def budget_handler(arg: str = "", **_: Any) -> str:
            """/budget [set N] — показать бюджет токенов или установить лимит."""
            if not registry._session:
                return "Сессия не инициализирована."
            tb = registry._session.token_budget

            # /budget set N
            parts = arg.strip().split()
            if parts and parts[0].lower() == "set":
                if len(parts) < 2:
                    return "**Использование:** `/budget set <N>` (N — лимит токенов, 0 = без лимита)"
                try:
                    limit = int(parts[1].replace("k", "000").replace("K", "000"))
                except ValueError:
                    return f"Неверное значение: `{parts[1]}`. Ожидается целое число."
                tb.session_limit = limit
                if limit == 0:
                    return "Лимит токенов снят (без ограничений)."
                return f"Лимит токенов установлен: **{limit:,}** токенов."

            # /budget — show status
            total = tb.total_tokens
            limit = tb.session_limit
            cost = getattr(tb, "_total_cost_usd", 0.0)

            def _k(n: int) -> str:
                return f"{n / 1000:.1f}k" if n >= 1000 else str(n)

            lines = ["## Бюджет токенов", ""]
            lines.append(f"**Использовано:** {_k(total)} токенов")
            if cost > 0:
                cost_fmt = f"${cost:.4f}".rstrip("0").rstrip(".")
                lines.append(f"**Стоимость:** {cost_fmt}")
            if limit > 0:
                remaining = max(0, limit - total)
                pct = int(total / limit * 100)
                bar_filled = pct // 5
                bar = "█" * bar_filled + "░" * (20 - bar_filled)
                lines.append(f"**Лимит:** {_k(limit)} токенов")
                lines.append(f"**Остаток:** {_k(remaining)} токенов ({100 - pct}%)")
                lines.append(f"`[{bar}]` {pct}%")
            else:
                lines.append("**Лимит:** без ограничений")

            by_role = getattr(tb, "_by_role", {})
            if by_role:
                lines.append("")
                lines.append("**По агентам:**")
                for role, tok in sorted(by_role.items(), key=lambda x: -x[1]):
                    lines.append(f"  · {role}: {_k(tok)}")

            lines.append("")
            lines.append("*`/budget set 100000` — установить лимит · `/budget set 0` — снять*")
            return "\n".join(lines)

        self.register(SlashCommand("budget", "Показать/установить бюджет токенов", budget_handler))

        # ── Task 167: /note ────────────────────────────────────────────────────

        async def note_handler(arg: str = "", **_: Any) -> str:
            """/note [text|clear] — показать/установить/очистить заметку сессии."""
            text = arg.strip()
            if text.lower() == "clear":
                registry.session_note = ""
                return "Заметка сессии очищена."
            if text:
                registry.session_note = text
                return f"Заметка сессии установлена:\n\n> {text}"
            # No arg — show current note
            if registry.session_note:
                return f"**Текущая заметка сессии:**\n\n> {registry.session_note}\n\n*`/note clear` — очистить*"
            return "Заметка сессии не установлена.\n\n*Использование: `/note <текст>` — установить заметку для всех агентов.*"

        self.register(SlashCommand(
            "note",
            "Установить заметку сессии, добавляемую в контекст агентов",
            note_handler,
        ))

        # ── Task 169: /alias ───────────────────────────────────────────────────

        async def alias_handler(arg: str = "", **_: Any) -> str:
            """/alias [name [command]] — управление псевдонимами команд."""
            parts = arg.strip().split(maxsplit=1)

            if not parts:
                # List all aliases
                if not registry._aliases:
                    return "Псевдонимы не определены.\n\n*`/alias <имя> <команда>` — создать псевдоним.*"
                lines = ["## Псевдонимы команд", ""]
                for name, cmd in sorted(registry._aliases.items()):
                    lines.append(f"  `/{name}` → `{cmd}`")
                return "\n".join(lines)

            name = parts[0].lstrip("/")
            if len(parts) == 1:
                # Show or delete alias
                if name == "clear":
                    registry._aliases.clear()
                    return "Все псевдонимы удалены."
                if name in registry._aliases:
                    return f"`/{name}` → `{registry._aliases[name]}`"
                return f"Псевдоним `/{name}` не найден."

            # Define alias: /alias name command
            cmd_str = parts[1].strip()
            if not cmd_str.startswith("/"):
                cmd_str = "/" + cmd_str
            registry._aliases[name] = cmd_str
            return f"Псевдоним создан: `/{name}` → `{cmd_str}`"

        self.register(SlashCommand(
            "alias",
            "Управление псевдонимами команд: /alias <имя> <команда>",
            alias_handler,
        ))

        # ── Task 171: /recent ──────────────────────────────────────────────────

        async def recent_handler(arg: str = "", **_: Any) -> str:
            """/recent [N] — файлы, изменённые в этой сессии."""
            try:
                n = int(arg.strip()) if arg.strip() else 10
                if n < 1:
                    n = 1
            except ValueError:
                n = 10

            files = list(dict.fromkeys(registry._edited_files))  # dedupe, preserve order
            if not files:
                return "В этой сессии файлы не изменялись."
            recent = files[-n:]
            lines = [f"## Изменённые файлы (последние {len(recent)} из {len(files)})", ""]
            for i, f in enumerate(recent, 1):
                lines.append(f"  {i}. `{f}`")
            lines.append(f"\n*`/undo` — откатить · `/diff` — просмотреть изменения*")
            return "\n".join(lines)

        self.register(SlashCommand("recent", "Файлы, изменённые в текущей сессии", recent_handler))

        # ── Task 172: /focus ───────────────────────────────────────────────────

        async def focus_handler(arg: str = "", **_: Any) -> str:
            """/focus [file|clear] — закрепить файл в контексте агентов."""
            text = arg.strip()
            if text.lower() == "clear":
                registry.focus_file = ""
                return "Фокус снят."
            if not text:
                if registry.focus_file:
                    return (
                        f"**Текущий фокус:** `{registry.focus_file}`\n\n"
                        f"*`/focus clear` — снять фокус*"
                    )
                return (
                    "Фокус не установлен.\n\n"
                    "*Использование: `/focus <путь_к_файлу>` — "
                    "содержимое файла будет добавлено в контекст каждого агента.*"
                )
            from pathlib import Path as _Path
            p = _Path(text)
            if not p.exists():
                return f"Файл не найден: `{text}`"
            if not p.is_file():
                return f"Это не файл: `{text}`"
            registry.focus_file = str(p)
            size = p.stat().st_size
            return (
                f"Фокус установлен: `{p}` ({size} байт)\n\n"
                f"*Содержимое файла будет добавляться в контекст каждого хода.*"
            )

        self.register(SlashCommand(
            "focus",
            "Закрепить файл в контексте агентов: /focus <файл> | /focus clear",
            focus_handler,
        ))

        # ── Task 173: /pin ─────────────────────────────────────────────────────

        async def pin_handler(arg: str = "", **_: Any) -> str:
            """/pin [add <text> | del <N> | clear | list] — закреплённые заметки."""
            text = arg.strip()
            if not text or text == "list":
                if not registry._pins:
                    return (
                        "Нет закреплённых заметок.\n\n"
                        "*`/pin add <текст>` — добавить закреплённую заметку.*"
                    )
                lines = ["## Закреплённые заметки", ""]
                for i, pin in enumerate(registry._pins, 1):
                    preview = pin[:100].replace("\n", " ")
                    if len(pin) > 100:
                        preview += "…"
                    lines.append(f"  **{i}.** {preview}")
                lines.append("")
                lines.append("*`/pin del <N>` — удалить · `/pin clear` — очистить все*")
                return "\n".join(lines)

            if text == "clear":
                count = len(registry._pins)
                registry._pins.clear()
                return f"Удалено {count} закреплённых заметок."

            if text.startswith("del "):
                num_str = text[4:].strip()
                try:
                    idx = int(num_str) - 1
                except ValueError:
                    return f"Неверный номер: `{num_str}`. Использование: `/pin del <N>`"
                if idx < 0 or idx >= len(registry._pins):
                    return f"Заметка #{num_str} не существует (всего {len(registry._pins)})."
                removed = registry._pins.pop(idx)
                preview = removed[:60].replace("\n", " ")
                return f"Заметка #{num_str} удалена: «{preview}»"

            if text == "add":
                return "Текст заметки не может быть пустым. Использование: `/pin add <текст>`"

            if text.startswith("add "):
                content = text[4:].strip()
                if not content:
                    return "Текст заметки не может быть пустым."
                registry._pins.append(content)
                n = len(registry._pins)
                preview = content[:60].replace("\n", " ")
                return f"Заметка #{n} закреплена: «{preview}»"

            # No subcommand — treat whole arg as text to add
            registry._pins.append(text)
            n = len(registry._pins)
            preview = text[:60].replace("\n", " ")
            return f"Заметка #{n} закреплена: «{preview}»"

        self.register(SlashCommand(
            "pin",
            "Закреплённые заметки, добавляемые в контекст: /pin add <текст> | /pin del <N> | /pin clear",
            pin_handler,
        ))

        # ── Task 174: /vars ────────────────────────────────────────────────────

        async def vars_handler(arg: str = "", **_: Any) -> str:
            """/vars [set NAME value | del NAME | clear | list] — шаблонные переменные."""
            text = arg.strip()

            if not text or text == "list":
                if not registry._vars:
                    return (
                        "Переменные сессии не определены.\n\n"
                        "*`/vars set NAME значение` — задать переменную.*\n"
                        "*В сообщениях используйте `{{NAME}}` для подстановки.*"
                    )
                lines = ["## Переменные сессии", ""]
                for name, val in sorted(registry._vars.items()):
                    preview = str(val)[:80].replace("\n", "↵")
                    lines.append(f"  `{{{{` **{name}** `}}}}` = `{preview}`")
                lines.append("")
                lines.append("*`{{NAME}}` в сообщении будет заменено на значение переменной.*")
                return "\n".join(lines)

            if text == "clear":
                count = len(registry._vars)
                registry._vars.clear()
                return f"Удалено {count} переменных."

            if text.startswith("del "):
                name = text[4:].strip()
                if not name:
                    return "Укажите имя переменной: `/vars del NAME`"
                if name not in registry._vars:
                    return f"Переменная `{name}` не найдена."
                del registry._vars[name]
                return f"Переменная `{name}` удалена."

            if text.startswith("set "):
                rest = text[4:].strip()
                parts = rest.split(maxsplit=1)
                if len(parts) < 2:
                    return "**Использование:** `/vars set NAME значение`"
                name, value = parts[0].upper(), parts[1]
                if not name.replace("_", "").isalnum():
                    return f"Имя переменной `{name}` содержит недопустимые символы (только буквы, цифры, _)."
                registry._vars[name] = value
                return f"Переменная `{name}` = `{value}`"

            return (
                "**Команды /vars:**\n\n"
                "- `/vars` — список переменных\n"
                "- `/vars set NAME значение` — задать переменную\n"
                "- `/vars del NAME` — удалить переменную\n"
                "- `/vars clear` — очистить все переменные\n\n"
                "*В сообщениях `{{NAME}}` заменяется на значение переменной.*"
            )

        self.register(SlashCommand(
            "vars",
            "Переменные сессии для шаблонной подстановки {{VAR}} в сообщениях",
            vars_handler,
        ))

        # ── Task 175: /timing ──────────────────────────────────────────────────

        async def timing_handler(arg: str = "", **_: Any) -> str:
            """/timing — статистика времени выполнения ходов."""
            times = registry._turn_times
            if not times:
                return (
                    "Данных о времени ходов ещё нет.\n\n"
                    "*Статистика появится после завершения первого хода.*"
                )

            arg = arg.strip().lower()
            n = len(times)
            total = sum(times)
            avg = total / n
            mn = min(times)
            mx = max(times)

            lines = ["## Время выполнения ходов", ""]
            lines.append(f"**Ходов:** {n}")
            lines.append(f"**Среднее:** {avg:.1f}с")
            lines.append(f"**Мин / Макс:** {mn:.1f}с / {mx:.1f}с")
            lines.append(f"**Итого:** {total:.1f}с")

            # Show individual turns if asked or few enough
            if arg == "all" or n <= 10:
                lines.append("")
                lines.append("**По ходам:**")
                for i, t in enumerate(times, 1):
                    bar_len = min(20, int(t / mx * 20)) if mx > 0 else 0
                    bar = "█" * bar_len + "░" * (20 - bar_len)
                    lines.append(f"  Ход {i:>3}: {t:5.1f}с  [{bar}]")
            elif n > 10:
                lines.append("")
                lines.append(f"*Показаны сводные данные. `/timing all` — все {n} ходов.*")

            return "\n".join(lines)

        self.register(SlashCommand(
            "timing",
            "Статистика времени выполнения ходов",
            timing_handler,
        ))

        # ── Task 176: /diff ────────────────────────────────────────────────────

        async def diff_handler(arg: str = "", **_: Any) -> str:
            """/diff [file] — показать git diff для файла или всех изменений."""
            import asyncio as _asyncio

            path_arg = arg.strip()

            async def _run_git(*cmd: str) -> tuple[str, int]:
                try:
                    p = await _asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=_asyncio.subprocess.PIPE,
                        stderr=_asyncio.subprocess.PIPE,
                    )
                    stdout, _ = await _asyncio.wait_for(p.communicate(), timeout=10)
                    return stdout.decode("utf-8", errors="replace"), p.returncode or 0
                except _asyncio.TimeoutError:
                    return "", -1
                except FileNotFoundError:
                    return "", -2

            if path_arg:
                out, rc = await _run_git("git", "diff", "HEAD", "--", path_arg)
                if rc == -2:
                    return "Git not found."
                if not out.strip():
                    # Try staged
                    out, rc = await _run_git("git", "diff", "--cached", "--", path_arg)
                if not out.strip():
                    return f"Нет изменений для `{path_arg}`."
            else:
                out, rc = await _run_git("git", "diff", "HEAD")
                if rc == -2:
                    return "Git not found."
                if not out.strip():
                    out, rc = await _run_git("git", "diff", "--cached")
                if not out.strip():
                    if registry._edited_files:
                        files_hint = ", ".join(f"`{f}`" for f in list(dict.fromkeys(registry._edited_files))[:5])
                        return (
                            f"Нет незафиксированных изменений.\n\n"
                            f"Изменённые в сессии файлы: {files_hint}\n\n"
                            "*Возможно, изменения уже зафиксированы (`/commit`).*"
                        )
                    return "Нет незафиксированных изменений."

            # Limit output
            _MAX_DIFF_LINES = 300
            lines = out.splitlines()
            truncated = len(lines) > _MAX_DIFF_LINES
            display = "\n".join(lines[:_MAX_DIFF_LINES])
            if truncated:
                display += f"\n... ({len(lines) - _MAX_DIFF_LINES} строк скрыто)"

            title = f"git diff — {path_arg}" if path_arg else "git diff HEAD"
            return f"```diff\n{display}\n```\n\n*{title}*"

        self.register(SlashCommand(
            "diff",
            "Показать git diff для файла или всех изменений: /diff [файл]",
            diff_handler,
        ))

        # ── Task 177: /snapshot ────────────────────────────────────────────────

        async def snapshot_handler(arg: str = "", **_: Any) -> str:
            """/snapshot [save <name> | load <name> | list | del <name>] — снэпшоты истории."""
            text = arg.strip()

            if not text or text == "list":
                if not registry._snapshots:
                    return (
                        "Снэпшоты не сохранены.\n\n"
                        "*`/snapshot save <имя>` — сохранить текущую историю диалога.*"
                    )
                lines = ["## Снэпшоты сессии", ""]
                for name, data in sorted(registry._snapshots.items()):
                    msg_count = len(data)
                    lines.append(f"  · **{name}** ({msg_count} сообщений)")
                lines.append("")
                lines.append("*`/snapshot load <имя>` — восстановить · `/snapshot del <имя>` — удалить*")
                return "\n".join(lines)

            if text.startswith("save "):
                name = text[5:].strip()
                if not name:
                    return "Укажите имя снэпшота: `/snapshot save <имя>`"
                if not registry._session:
                    # Allow saving empty snapshot for testing
                    registry._snapshots[name] = []
                    return f"Снэпшот **{name}** сохранён (0 сообщений)."
                orch = registry._session.orchestrator
                history = list(getattr(orch, "_conversation_history", []))
                registry._snapshots[name] = history
                return f"Снэпшот **{name}** сохранён ({len(history)} сообщений)."

            if text.startswith("load "):
                name = text[5:].strip()
                if not name:
                    return "Укажите имя снэпшота: `/snapshot load <имя>`"
                if name not in registry._snapshots:
                    available = ", ".join(f"`{n}`" for n in sorted(registry._snapshots))
                    hint = f"\n\nДоступные: {available}" if available else ""
                    return f"Снэпшот `{name}` не найден.{hint}"
                if not registry._session:
                    return f"Сессия не инициализирована. Не могу загрузить снэпшот `{name}`."
                history = registry._snapshots[name]
                registry._session.orchestrator.restore_history(list(history))
                return f"Снэпшот **{name}** восстановлен ({len(history)} сообщений)."

            if text.startswith("del "):
                name = text[4:].strip()
                if not name:
                    return "Укажите имя снэпшота: `/snapshot del <имя>`"
                if name not in registry._snapshots:
                    return f"Снэпшот `{name}` не найден."
                del registry._snapshots[name]
                return f"Снэпшот `{name}` удалён."

            if text == "clear":
                count = len(registry._snapshots)
                registry._snapshots.clear()
                return f"Удалено {count} снэпшотов."

            return (
                "**Команды /snapshot:**\n\n"
                "- `/snapshot save <имя>` — сохранить текущую историю диалога\n"
                "- `/snapshot load <имя>` — восстановить историю из снэпшота\n"
                "- `/snapshot del <имя>` — удалить снэпшот\n"
                "- `/snapshot list` — список сохранённых снэпшотов\n"
                "- `/snapshot clear` — удалить все снэпшоты"
            )

        self.register(SlashCommand(
            "snapshot",
            "Снэпшоты истории диалога: /snapshot save|load|del|list",
            snapshot_handler,
        ))

        # ── Task 178: /grep ────────────────────────────────────────────────────

        async def grep_handler(arg: str = "", **_: Any) -> str:
            """/grep <pattern> [path] — поиск паттерна в исходном коде."""
            import asyncio as _asyncio
            import re as _re

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/grep <паттерн> [путь]`\n\n"
                    "Ищет паттерн (regex) в исходном коде проекта.\n\n"
                    "**Примеры:**\n"
                    "  `/grep def authenticate`\n"
                    "  `/grep TODO src/lidco/core/`\n"
                    "  `/grep 'class.*Error' src/`"
                )

            # Split off optional path (last token if it looks like a path)
            parts = text.split()
            search_path = "."
            pattern = text
            if len(parts) >= 2:
                last = parts[-1]
                # Treat as path if it has / or \ or . in it (not a regex special)
                if ("/" in last or "\\" in last or last.endswith(".py")):
                    search_path = last
                    pattern = " ".join(parts[:-1])

            from pathlib import Path as _Path

            root = _Path(search_path)
            if not root.exists():
                return f"Путь не найден: `{search_path}`"

            try:
                pat_re = _re.compile(pattern)
            except _re.error as exc:
                return f"Неверный regex: `{pattern}` — {exc}"

            if root.is_file():
                py_files = [root]
            else:
                py_files = sorted(root.rglob("*.py"))

            _MAX_RESULTS = 50
            results: list[tuple[str, int, str]] = []
            for pyf in py_files:
                if len(results) >= _MAX_RESULTS:
                    break
                # Skip common non-project dirs
                parts_path = pyf.parts
                if any(p in parts_path for p in (".git", "__pycache__", ".venv", "venv", "node_modules")):
                    continue
                try:
                    for lineno, line in enumerate(
                        pyf.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
                    ):
                        if pat_re.search(line):
                            rel = str(pyf)
                            results.append((rel, lineno, line.rstrip()))
                            if len(results) >= _MAX_RESULTS:
                                break
                except OSError:
                    pass

            if not results:
                return f"Паттерн `{pattern}` не найден в `{search_path}`."

            lines = [f"## Grep: `{pattern}` ({len(results)} совпадений)", ""]
            current_file = ""
            for file_path, lineno, line_content in results:
                if file_path != current_file:
                    current_file = file_path
                    lines.append(f"**{file_path}**")
                preview = line_content.strip()[:120]
                lines.append(f"  `{lineno}:` {preview}")

            if len(results) >= _MAX_RESULTS:
                lines.append(f"\n*Показано {_MAX_RESULTS} совпадений. Уточните паттерн или путь для сужения поиска.*")

            return "\n".join(lines)

        self.register(SlashCommand(
            "grep",
            "Поиск паттерна (regex) в исходном коде: /grep <паттерн> [путь]",
            grep_handler,
        ))

        # ── Task 179: /watch ───────────────────────────────────────────────────

        async def watch_handler(arg: str = "", **_: Any) -> str:
            """/watch [add <path> | remove <path> | list | clear | status] — отслеживать изменения файлов."""
            from pathlib import Path as _Path
            import os as _os

            text = arg.strip()

            def _snapshot(paths: list[str]) -> dict[str, float]:
                """Return mtime mapping for all watched paths."""
                result: dict[str, float] = {}
                for p in paths:
                    try:
                        result[p] = _os.path.getmtime(p)
                    except OSError:
                        result[p] = -1.0
                return result

            if not text or text == "list" or text == "status":
                watched = registry._watched_files
                if not watched:
                    return (
                        "Нет отслеживаемых файлов.\n\n"
                        "*`/watch add <путь>` — начать отслеживание файла.*"
                    )
                lines = ["## Отслеживаемые файлы", ""]
                snap = registry._watch_snapshot
                for p in watched:
                    mtime = snap.get(p, -1.0)
                    try:
                        current = _os.path.getmtime(p)
                        changed = current != mtime and mtime >= 0
                        status = " ⚡ изменён" if changed else " ✓"
                    except OSError:
                        status = " ✗ не найден"
                    lines.append(f"  · `{p}`{status}")
                lines.append("")
                lines.append("*`/watch remove <путь>` — убрать · `/watch clear` — убрать все · `/watch check` — проверить изменения*")
                return "\n".join(lines)

            if text.startswith("add "):
                path_str = text[4:].strip()
                if not path_str:
                    return "Укажите путь: `/watch add <путь>`"
                p = _Path(path_str)
                if not p.exists():
                    return f"Путь не найден: `{path_str}`"
                path_str_resolved = str(p)
                if path_str_resolved in registry._watched_files:
                    return f"Файл `{path_str_resolved}` уже отслеживается."
                registry._watched_files.append(path_str_resolved)
                try:
                    registry._watch_snapshot[path_str_resolved] = _os.path.getmtime(path_str_resolved)
                except OSError:
                    registry._watch_snapshot[path_str_resolved] = -1.0
                return f"Отслеживание начато: `{path_str_resolved}`"

            if text.startswith("remove ") or text.startswith("rm "):
                sep = "remove " if text.startswith("remove ") else "rm "
                path_str = text[len(sep):].strip()
                if path_str in registry._watched_files:
                    registry._watched_files.remove(path_str)
                    registry._watch_snapshot.pop(path_str, None)
                    return f"Отслеживание остановлено: `{path_str}`"
                return f"Файл `{path_str}` не отслеживается."

            if text == "clear":
                count = len(registry._watched_files)
                registry._watched_files.clear()
                registry._watch_snapshot.clear()
                return f"Убрано {count} отслеживаемых файлов."

            if text == "check":
                watched = registry._watched_files
                if not watched:
                    return "Нет отслеживаемых файлов."
                changed: list[str] = []
                for p in watched:
                    try:
                        current = _os.path.getmtime(p)
                        prev = registry._watch_snapshot.get(p, -1.0)
                        if current != prev:
                            changed.append(p)
                            registry._watch_snapshot[p] = current
                    except OSError:
                        pass
                if not changed:
                    return f"Изменений нет (проверено {len(watched)} файлов)."
                lines = [f"**Изменено {len(changed)} файлов:**", ""]
                for p in changed:
                    lines.append(f"  · `{p}`")
                lines.append("\n*Используйте `/diff <файл>` для просмотра изменений.*")
                return "\n".join(lines)

            return (
                "**Команды /watch:**\n\n"
                "- `/watch add <путь>` — начать отслеживание\n"
                "- `/watch remove <путь>` — остановить отслеживание\n"
                "- `/watch list` — список отслеживаемых файлов\n"
                "- `/watch check` — проверить изменения\n"
                "- `/watch clear` — убрать все\n"
            )

        self.register(SlashCommand(
            "watch",
            "Отслеживать изменения файлов: /watch add|remove|list|check|clear",
            watch_handler,
        ))

        # ── Task 180: /tag ─────────────────────────────────────────────────────

        async def tag_handler(arg: str = "", **_: Any) -> str:
            """/tag [add <label> | list | del <label> | jump <label>] — теги для ходов диалога."""
            text = arg.strip()

            if not text or text == "list":
                if not registry._tags:
                    return (
                        "Нет тегов.\n\n"
                        "*`/tag add <метка>` — пометить текущий ход тегом.*"
                    )
                lines = ["## Теги диалога", ""]
                for label, turn_idx in sorted(registry._tags.items()):
                    lines.append(f"  · **#{label}** → ход {turn_idx}")
                lines.append("")
                lines.append("*`/tag del <метка>` — удалить тег*")
                return "\n".join(lines)

            if text.startswith("add "):
                label = text[4:].strip()
                if not label:
                    return "Укажите метку: `/tag add <метка>`"
                if not label.replace("-", "").replace("_", "").isalnum():
                    return f"Метка `{label}` содержит недопустимые символы (только буквы, цифры, -, _)."
                # Use current history length as the turn marker
                turn_idx = 0
                if registry._session:
                    orch = registry._session.orchestrator
                    turn_idx = len(getattr(orch, "_conversation_history", []))
                else:
                    turn_idx = len(registry._turn_times)
                registry._tags[label] = turn_idx
                return f"Тег **#{label}** установлен на ход {turn_idx}."

            if text.startswith("del "):
                label = text[4:].strip()
                if label not in registry._tags:
                    return f"Тег `#{label}` не найден."
                del registry._tags[label]
                return f"Тег **#{label}** удалён."

            if text == "clear":
                count = len(registry._tags)
                registry._tags.clear()
                return f"Удалено {count} тегов."

            if text.startswith("jump "):
                label = text[5:].strip()
                if label not in registry._tags:
                    available = ", ".join(f"`#{k}`" for k in sorted(registry._tags))
                    hint = f"\n\nДоступные: {available}" if available else ""
                    return f"Тег `#{label}` не найден.{hint}"
                turn_idx = registry._tags[label]
                if not registry._session:
                    return f"Сессия не инициализирована. Тег **#{label}** указывает на ход {turn_idx}."
                orch = registry._session.orchestrator
                history = list(getattr(orch, "_conversation_history", []))
                if turn_idx > len(history):
                    return f"Тег **#{label}** указывает на ход {turn_idx}, но история содержит только {len(history)} сообщений."
                orch.restore_history(history[:turn_idx])
                return f"История восстановлена до тега **#{label}** (ход {turn_idx}, {turn_idx} сообщений)."

            # Bare word — treat as shortcut for add
            label = text
            if not label.replace("-", "").replace("_", "").isalnum():
                return f"Метка `{label}` содержит недопустимые символы. Использование: `/tag add <метка>`"
            turn_idx = len(registry._turn_times)
            registry._tags[label] = turn_idx
            return f"Тег **#{label}** установлен на ход {turn_idx}."

        self.register(SlashCommand(
            "tag",
            "Теги для ходов диалога: /tag add <метка> | /tag jump <метка> | /tag list",
            tag_handler,
        ))

        # ── Task 181: /summary ─────────────────────────────────────────────────

        async def summary_handler(arg: str = "", **_: Any) -> str:
            """/summary — краткое резюме текущего диалога."""
            if not registry._session:
                return "Сессия не инициализирована."

            orch = registry._session.orchestrator
            history = list(getattr(orch, "_conversation_history", []))

            if not history:
                return "История диалога пуста."

            # Build a condensed transcript (user messages only, or last N pairs)
            _MAX_CHARS = 6000
            pairs: list[str] = []
            total_chars = 0
            for msg in reversed(history):
                role = msg.get("role", "")
                content = str(msg.get("content", ""))[:400]
                if role in ("user", "assistant"):
                    entry = f"{role.upper()}: {content}"
                    total_chars += len(entry)
                    pairs.insert(0, entry)
                    if total_chars >= _MAX_CHARS:
                        break

            transcript = "\n\n".join(pairs)

            from lidco.llm.base import Message as LLMMessage
            try:
                resp = await registry._session.llm.complete(
                    [LLMMessage(role="user", content=(
                        "Summarize this conversation in 3-5 bullet points in Russian. "
                        "Focus on what was accomplished, what was decided, and what's pending.\n\n"
                        f"CONVERSATION:\n{transcript}\n\n"
                        "Output ONLY the bullet points, no preamble."
                    ))],
                    temperature=0.3,
                    max_tokens=300,
                )
                summary_text = (resp.content or "").strip()
            except Exception as exc:
                return f"Не удалось сгенерировать резюме: {exc}"

            turn_count = sum(1 for m in history if m.get("role") == "user")
            return (
                f"## Резюме диалога ({turn_count} ходов)\n\n"
                f"{summary_text}\n\n"
                f"*`/history` — полная история · `/compact` — сжать контекст*"
            )

        self.register(SlashCommand(
            "summary",
            "Краткое AI-резюме текущего диалога",
            summary_handler,
        ))

        # ── Task 182: /profile ─────────────────────────────────────────────────

        async def profile_handler(arg: str = "", **_: Any) -> str:
            """/profile — статистика производительности по агентам."""
            if not registry._agent_stats:
                return (
                    "Статистика агентов пока недоступна.\n\n"
                    "*Данные появятся после первого обращения к агенту.*"
                )

            arg = arg.strip().lower()

            # /profile reset
            if arg == "reset":
                registry._agent_stats.clear()
                return "Статистика агентов сброшена."

            # /profile <agent> — single agent details
            if arg and arg != "all":
                stats = registry._agent_stats.get(arg)
                if not stats:
                    available = ", ".join(f"`{k}`" for k in sorted(registry._agent_stats))
                    return (
                        f"Агент `{arg}` не найден в статистике.\n\n"
                        f"Доступные: {available}"
                    )
                calls = stats.get("calls", 0)
                tokens = stats.get("tokens", 0)
                elapsed = stats.get("elapsed", 0.0)
                avg_t = elapsed / calls if calls else 0.0
                avg_tok = tokens // calls if calls else 0
                lines = [
                    f"## Профиль: {arg}", "",
                    f"**Вызовов:** {calls}",
                    f"**Токенов:** {tokens:,}",
                    f"**Время:** {elapsed:.1f}с итого · {avg_t:.1f}с среднее",
                    f"**Токенов/вызов:** {avg_tok:,}",
                ]
                return "\n".join(lines)

            # /profile — full table
            def _k(n: int) -> str:
                return f"{n / 1000:.1f}k" if n >= 1000 else str(n)

            lines = ["## Профиль агентов", ""]
            sorted_agents = sorted(
                registry._agent_stats.items(),
                key=lambda x: -x[1].get("tokens", 0),
            )
            for agent_name, stats in sorted_agents:
                calls = stats.get("calls", 0)
                tokens = stats.get("tokens", 0)
                elapsed = stats.get("elapsed", 0.0)
                avg_t = elapsed / calls if calls else 0.0
                lines.append(
                    f"  **{agent_name}** — {calls} вызовов · "
                    f"{_k(tokens)} токенов · {elapsed:.1f}с итого · {avg_t:.1f}с avg"
                )

            lines.append("")
            lines.append("*`/profile <агент>` — детали · `/profile reset` — сбросить*")
            return "\n".join(lines)

        self.register(SlashCommand(
            "profile",
            "Статистика производительности по агентам",
            profile_handler,
        ))

        # ── Task 183: /template ────────────────────────────────────────────────

        async def template_handler(arg: str = "", **_: Any) -> str:
            """/template [save <name> <text> | use <name> [vars] | list | del <name>] — шаблоны сообщений."""
            import re as _re
            text = arg.strip()

            if not text or text == "list":
                if not registry._templates:
                    return (
                        "Шаблоны не определены.\n\n"
                        "*`/template save <имя> <текст>` — сохранить шаблон.*\n"
                        "*Используйте `{{PLACEHOLDER}}` для переменных.*"
                    )
                lines = ["## Шаблоны сообщений", ""]
                for name, tmpl in sorted(registry._templates.items()):
                    preview = tmpl[:80].replace("\n", " ")
                    if len(tmpl) > 80:
                        preview += "…"
                    # Find placeholders
                    placeholders = _re.findall(r"\{\{([A-Z0-9_]+)\}\}", tmpl)
                    ph_hint = f" [{', '.join(placeholders)}]" if placeholders else ""
                    lines.append(f"  · **{name}**{ph_hint}: `{preview}`")
                lines.append("")
                lines.append("*`/template use <имя>` — применить · `/template del <имя>` — удалить*")
                return "\n".join(lines)

            if text.startswith("save "):
                rest = text[5:].strip()
                parts = rest.split(maxsplit=1)
                if len(parts) < 2:
                    return "**Использование:** `/template save <имя> <текст шаблона>`"
                name, tmpl_text = parts[0], parts[1]
                if not name.replace("-", "").replace("_", "").isalnum():
                    return f"Имя шаблона `{name}` содержит недопустимые символы."
                registry._templates[name] = tmpl_text
                placeholders = _re.findall(r"\{\{([A-Z0-9_]+)\}\}", tmpl_text)
                ph_note = f"\n\nПеременные: {', '.join(f'`{{{{{p}}}}}`' for p in placeholders)}" if placeholders else ""
                return f"Шаблон **{name}** сохранён.{ph_note}"

            if text.startswith("use "):
                rest = text[4:].strip()
                parts = rest.split(maxsplit=1)
                if not parts:
                    return "Укажите имя шаблона: `/template use <имя> [KEY=value ...]`"
                name = parts[0]
                if name not in registry._templates:
                    available = ", ".join(f"`{n}`" for n in sorted(registry._templates))
                    hint = f"\n\nДоступные: {available}" if available else ""
                    return f"Шаблон `{name}` не найден.{hint}"
                tmpl_text = registry._templates[name]
                # Parse KEY=value pairs from remainder
                overrides: dict[str, str] = {}
                if len(parts) > 1:
                    for kv in parts[1].split():
                        if "=" in kv:
                            k, v = kv.split("=", 1)
                            overrides[k.upper()] = v
                # Apply: first /vars, then overrides
                merged = {**registry._vars, **overrides}
                result_text = _re.sub(
                    r"\{\{([A-Z0-9_]+)\}\}",
                    lambda m: merged.get(m.group(1), m.group(0)),
                    tmpl_text,
                )
                # Check for unfilled placeholders
                remaining = _re.findall(r"\{\{([A-Z0-9_]+)\}\}", result_text)
                if remaining:
                    return (
                        f"Шаблон **{name}** содержит незаполненные переменные: "
                        f"{', '.join(f'`{{{{{p}}}}}`' for p in remaining)}\n\n"
                        f"Используйте `/template use {name} KEY=value ...` для подстановки.\n\n"
                        f"Текущий результат:\n\n> {result_text}"
                    )
                return f"__RETRY__:{result_text}"

            if text.startswith("del "):
                name = text[4:].strip()
                if name not in registry._templates:
                    return f"Шаблон `{name}` не найден."
                del registry._templates[name]
                return f"Шаблон **{name}** удалён."

            if text.startswith("show "):
                name = text[5:].strip()
                if name not in registry._templates:
                    return f"Шаблон `{name}` не найден."
                return f"**{name}:**\n\n```\n{registry._templates[name]}\n```"

            if text == "clear":
                count = len(registry._templates)
                registry._templates.clear()
                return f"Удалено {count} шаблонов."

            return (
                "**Команды /template:**\n\n"
                "- `/template save <имя> <текст>` — сохранить шаблон\n"
                "- `/template use <имя> [KEY=value ...]` — применить шаблон\n"
                "- `/template show <имя>` — показать шаблон\n"
                "- `/template del <имя>` — удалить\n"
                "- `/template list` — список всех шаблонов\n"
                "- `/template clear` — удалить все\n\n"
                "*Переменные в тексте: `{{PLACEHOLDER}}`.*"
            )

        self.register(SlashCommand(
            "template",
            "Шаблоны сообщений с переменными: /template save|use|list|del",
            template_handler,
        ))

        # ── Task 184: /pipe ────────────────────────────────────────────────────

        async def pipe_handler(arg: str = "", **_: Any) -> str:
            """/pipe <agent1> | <agent2> [| ...] <message> — передать ответ через цепочку агентов."""
            if not arg.strip():
                return (
                    "**Использование:** `/pipe <агент1> | <агент2> <сообщение>`\n\n"
                    "Передаёт ответ первого агента на вход следующему.\n\n"
                    "**Пример:** `/pipe coder | tester напиши функцию сортировки`\n\n"
                    "*Первый агент получает оригинальное сообщение, каждый следующий — ответ предыдущего.*"
                )

            if not registry._session:
                return "Сессия не инициализирована."

            # Parse: split by " | " but keep last segment as message for first agent
            # Format: "agent1 | agent2 | agent3 message"
            # or:    "agent1 | agent2 message" where message goes to agent1
            raw = arg.strip()
            segments = [s.strip() for s in raw.split("|")]

            if len(segments) < 2:
                return (
                    "Укажите хотя бы двух агентов через `|`.\n\n"
                    "**Пример:** `/pipe coder | tester напиши функцию`"
                )

            # Last segment may contain "agentN message" or just "agentN"
            # First segment: "agent1 message" (message sent to first agent)
            first_parts = segments[0].split(maxsplit=1)
            first_agent = first_parts[0]
            message = first_parts[1] if len(first_parts) > 1 else ""

            # Middle agents: pure agent names
            middle_agents = []
            for seg in segments[1:-1]:
                middle_agents.append(seg.strip().split()[0])

            # Last agent: may have trailing message appended
            last_parts = segments[-1].split(maxsplit=1)
            last_agent = last_parts[0]
            if not message and len(last_parts) > 1:
                message = last_parts[1]

            agents = [first_agent] + middle_agents + [last_agent]

            if not message:
                return "Укажите сообщение для первого агента."

            # Validate all agents exist
            available = registry._session.agent_registry.list_names()
            for a in agents:
                if a not in available:
                    return (
                        f"Агент **{a}** не найден.\n"
                        f"Доступные: {', '.join(f'`{n}`' for n in available)}"
                    )

            # Execute pipeline
            current_message = message
            results: list[tuple[str, str]] = []
            for i, agent_name in enumerate(agents):
                try:
                    response = await registry._session.orchestrator.handle(
                        current_message,
                        agent_name=agent_name,
                    )
                    current_message = response.content or ""
                    results.append((agent_name, current_message))
                except Exception as exc:
                    results.append((agent_name, f"[Ошибка: {exc}]"))
                    break

            # Format output
            lines = [f"## Pipe: {' → '.join(agents)}", ""]
            for step, (agent_name, output) in enumerate(results, 1):
                preview = output[:300]
                if len(output) > 300:
                    preview += "…"
                lines.append(f"**Шаг {step} ({agent_name}):**")
                lines.append(preview)
                if step < len(results):
                    lines.append("")

            return "\n".join(lines)

        self.register(SlashCommand(
            "pipe",
            "Цепочка агентов: /pipe агент1 | агент2 сообщение",
            pipe_handler,
        ))

        # ── Task 185: /mode ────────────────────────────────────────────────────

        _MODES: dict[str, dict] = {
            "focus": {
                "desc": "Минимальный вывод, только суть ответа. Без подсказок и предложений.",
                "no_suggestions": True,
                "no_tool_display": True,
            },
            "normal": {
                "desc": "Стандартный режим (по умолчанию).",
                "no_suggestions": False,
                "no_tool_display": False,
            },
            "verbose": {
                "desc": "Подробный вывод: все инструменты, токены, подсказки.",
                "no_suggestions": False,
                "no_tool_display": False,
                "show_tokens": True,
            },
            "quiet": {
                "desc": "Тихий режим: вывод только финального ответа, без технических деталей.",
                "no_suggestions": True,
                "no_tool_display": True,
            },
        }

        async def mode_handler(arg: str = "", **_: Any) -> str:
            """/mode [focus|normal|verbose|quiet] — переключить режим взаимодействия."""
            text = arg.strip().lower()

            if not text:
                current = registry.session_mode
                mode_info = _MODES.get(current, {})
                lines = [f"**Режим:** `{current}`", "", mode_info.get("desc", ""), ""]
                lines.append("**Доступные режимы:**")
                for name, info in _MODES.items():
                    marker = " ← текущий" if name == current else ""
                    lines.append(f"  · `{name}`{marker} — {info['desc']}")
                lines.append("\n*`/mode <название>` — переключить режим*")
                return "\n".join(lines)

            if text not in _MODES:
                names = ", ".join(f"`{n}`" for n in _MODES)
                return f"Неизвестный режим `{text}`.\n\nДоступные: {names}"

            registry.session_mode = text
            info = _MODES[text]
            return f"Режим переключён на **{text}**.\n\n{info['desc']}"

        self.register(SlashCommand(
            "mode",
            "Режим взаимодействия: /mode focus|normal|verbose|quiet",
            mode_handler,
        ))

        # ── Task 186: /autosave ────────────────────────────────────────────────

        async def autosave_handler(arg: str = "", **_: Any) -> str:
            """/autosave [on|off|N|status] — автоэкспорт сессии каждые N ходов."""
            text = arg.strip().lower()

            if not text or text == "status":
                interval = registry._autosave_interval
                count = registry._autosave_turn_count
                if interval == 0:
                    return (
                        "Автосохранение **отключено**.\n\n"
                        "*`/autosave on` — включить (каждые 10 ходов) · "
                        "`/autosave <N>` — задать интервал*"
                    )
                next_in = interval - (count % interval)
                return (
                    f"Автосохранение **включено** (каждые {interval} ходов).\n"
                    f"Ходов до следующего сохранения: {next_in}\n\n"
                    f"*`/autosave off` — отключить · `/autosave <N>` — изменить интервал*"
                )

            if text in ("off", "disable", "0"):
                registry._autosave_interval = 0
                return "Автосохранение **отключено**."

            if text in ("on", "enable"):
                registry._autosave_interval = 10
                return "Автосохранение **включено** (каждые 10 ходов)."

            try:
                n = int(text)
                if n < 1:
                    return "Интервал должен быть ≥ 1."
                registry._autosave_interval = n
                return f"Автосохранение **включено** (каждые {n} ходов)."
            except ValueError:
                return (
                    f"Неверный аргумент `{arg}`.\n\n"
                    "**Использование:** `/autosave on|off|<N>`"
                )

        self.register(SlashCommand(
            "autosave",
            "Автоэкспорт сессии каждые N ходов: /autosave on|off|N",
            autosave_handler,
        ))

        # ── Task 187: /remind ──────────────────────────────────────────────────

        async def remind_handler(arg: str = "", **_: Any) -> str:
            """/remind [in <N> <text> | list | del <N> | clear] — напоминания по ходам."""
            text = arg.strip()

            if not text or text == "list":
                if not registry._reminders:
                    return (
                        "Нет активных напоминаний.\n\n"
                        "*`/remind in <N> <текст>` — напомнить через N ходов.*"
                    )
                lines = ["## Напоминания", ""]
                current_turn = len(registry._turn_times)
                for i, rem in enumerate(registry._reminders, 1):
                    fire_at = rem["fire_at"]
                    turns_left = max(0, fire_at - current_turn)
                    lines.append(
                        f"  **{i}.** (через {turns_left} ходов): {rem['text']}"
                    )
                lines.append("")
                lines.append("*`/remind del <N>` — удалить · `/remind clear` — удалить все*")
                return "\n".join(lines)

            if text.startswith("in "):
                rest = text[3:].strip()
                parts = rest.split(maxsplit=1)
                if len(parts) < 2:
                    return "**Использование:** `/remind in <N> <текст напоминания>`"
                try:
                    n = int(parts[0])
                    if n < 1:
                        return "Количество ходов должно быть ≥ 1."
                except ValueError:
                    return f"Неверное количество ходов: `{parts[0]}`"
                reminder_text = parts[1].strip()
                if not reminder_text:
                    return "Текст напоминания не может быть пустым."
                fire_at = len(registry._turn_times) + n
                registry._reminders.append({"fire_at": fire_at, "text": reminder_text})
                return f"Напоминание установлено через {n} ходов: «{reminder_text}»"

            if text.startswith("del "):
                num_str = text[4:].strip()
                try:
                    idx = int(num_str) - 1
                except ValueError:
                    return f"Неверный номер: `{num_str}`"
                if idx < 0 or idx >= len(registry._reminders):
                    return f"Напоминание #{num_str} не существует (всего {len(registry._reminders)})."
                removed = registry._reminders.pop(idx)
                return f"Напоминание #{num_str} удалено: «{removed['text']}»"

            if text == "clear":
                count = len(registry._reminders)
                registry._reminders.clear()
                return f"Удалено {count} напоминаний."

            return (
                "**Команды /remind:**\n\n"
                "- `/remind in <N> <текст>` — напомнить через N ходов\n"
                "- `/remind list` — список напоминаний\n"
                "- `/remind del <N>` — удалить напоминание\n"
                "- `/remind clear` — удалить все напоминания"
            )

        self.register(SlashCommand(
            "remind",
            "Напоминания по ходам: /remind in <N> <текст> | /remind list",
            remind_handler,
        ))

        # ── Task 188: /bookmark ────────────────────────────────────────────────

        async def bookmark_handler(arg: str = "", **_: Any) -> str:
            """/bookmark [add <name> <file>[:<line>] | list | del <name> | go <name>] — закладки файлов."""
            from pathlib import Path as _Path
            text = arg.strip()

            if not text or text == "list":
                if not registry._bookmarks:
                    return (
                        "Нет закладок.\n\n"
                        "*`/bookmark add <имя> <файл>[:<строка>]` — добавить закладку.*"
                    )
                lines = ["## Закладки", ""]
                for name, bm in sorted(registry._bookmarks.items()):
                    loc = bm["file"]
                    if bm.get("line"):
                        loc += f":{bm['line']}"
                    lines.append(f"  · **{name}** → `{loc}`")
                lines.append("")
                lines.append("*`/bookmark go <имя>` — перейти (показать содержимое) · `/bookmark del <имя>` — удалить*")
                return "\n".join(lines)

            if text.startswith("add "):
                rest = text[4:].strip()
                parts = rest.split(maxsplit=1)
                if len(parts) < 2:
                    return "**Использование:** `/bookmark add <имя> <файл>[:<строка>]`"
                name = parts[0]
                location = parts[1].strip()
                # Parse file:line
                line_num: int | None = None
                if ":" in location:
                    file_part, line_part = location.rsplit(":", 1)
                    try:
                        line_num = int(line_part)
                        location = file_part
                    except ValueError:
                        pass  # treat whole thing as filename
                p = _Path(location)
                if not p.exists():
                    return f"Файл не найден: `{location}`"
                if not p.is_file():
                    return f"Это не файл: `{location}`"
                registry._bookmarks[name] = {"file": str(p), "line": line_num}
                loc_str = f"{p}:{line_num}" if line_num else str(p)
                return f"Закладка **{name}** → `{loc_str}`"

            if text.startswith("del "):
                name = text[4:].strip()
                if name not in registry._bookmarks:
                    return f"Закладка `{name}` не найдена."
                del registry._bookmarks[name]
                return f"Закладка **{name}** удалена."

            if text == "clear":
                count = len(registry._bookmarks)
                registry._bookmarks.clear()
                return f"Удалено {count} закладок."

            if text.startswith("go "):
                name = text[3:].strip()
                if name not in registry._bookmarks:
                    available = ", ".join(f"`{n}`" for n in sorted(registry._bookmarks))
                    hint = f"\n\nДоступные: {available}" if available else ""
                    return f"Закладка `{name}` не найдена.{hint}"
                bm = registry._bookmarks[name]
                file_path = bm["file"]
                line_num = bm.get("line")
                try:
                    content = _Path(file_path).read_text(encoding="utf-8", errors="replace")
                    lines_list = content.splitlines()
                    total = len(lines_list)
                    if line_num and 1 <= line_num <= total:
                        # Show ±5 lines around target
                        start = max(0, line_num - 6)
                        end = min(total, line_num + 5)
                        excerpt = "\n".join(
                            f"{'→' if i + 1 == line_num else ' '} {i + start + 1:4}: {lines_list[i + start]}"
                            for i in range(end - start)
                        )
                        return f"**{file_path}:{line_num}** ({total} строк)\n\n```python\n{excerpt}\n```"
                    else:
                        # Show first 30 lines
                        preview = "\n".join(f"  {i:4}: {l}" for i, l in enumerate(lines_list[:30], 1))
                        suffix = f"\n  ... ({total - 30} строк скрыто)" if total > 30 else ""
                        return f"**{file_path}** ({total} строк)\n\n```python\n{preview}{suffix}\n```"
                except OSError as exc:
                    return f"Не удалось прочитать `{file_path}`: {exc}"

            return (
                "**Команды /bookmark:**\n\n"
                "- `/bookmark add <имя> <файл>[:<строка>]` — добавить закладку\n"
                "- `/bookmark go <имя>` — показать содержимое файла у закладки\n"
                "- `/bookmark del <имя>` — удалить\n"
                "- `/bookmark list` — список закладок\n"
                "- `/bookmark clear` — удалить все"
            )

        self.register(SlashCommand(
            "bookmark",
            "Закладки файлов: /bookmark add|go|del|list",
            bookmark_handler,
        ))

        # ── Task 189: /fmt ─────────────────────────────────────────────────────

        async def fmt_handler(arg: str = "", **_: Any) -> str:
            """/fmt [file|--check] — форматировать Python файл через ruff format."""
            import asyncio as _asyncio
            from pathlib import Path as _Path

            text = arg.strip()
            check_only = False

            if text.endswith("--check"):
                check_only = True
                text = text[: -len("--check")].strip()

            if not text:
                return (
                    "**Использование:** `/fmt <файл.py> [--check]`\n\n"
                    "Форматирует Python файл с помощью `ruff format`.\n\n"
                    "**Примеры:**\n"
                    "  `/fmt src/lidco/core/session.py`\n"
                    "  `/fmt src/lidco/ --check` — проверить без изменений"
                )

            p = _Path(text)
            if not p.exists():
                return f"Путь не найден: `{text}`"

            cmd = ["python", "-m", "ruff", "format"]
            if check_only:
                cmd.append("--check")
            cmd.append(str(p))

            try:
                proc = await _asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=_asyncio.subprocess.PIPE,
                    stderr=_asyncio.subprocess.PIPE,
                )
                stdout, stderr = await _asyncio.wait_for(proc.communicate(), timeout=30)
                rc = proc.returncode or 0
            except _asyncio.TimeoutError:
                return "Форматирование превысило лимит времени (30с)."
            except FileNotFoundError:
                return "ruff не найден. Установите: `pip install ruff`"

            out = (stdout + stderr).decode("utf-8", errors="replace").strip()

            if check_only:
                if rc == 0:
                    return f"`{text}` — форматирование не требуется ✓"
                return f"`{text}` — требуется форматирование ✗\n\n```\n{out}\n```" if out else f"`{text}` — требуется форматирование ✗"

            if rc == 0:
                note = f"\n\n```\n{out}\n```" if out else ""
                return f"`{text}` — отформатировано ✓{note}"
            return f"Ошибка форматирования:\n\n```\n{out}\n```"

        self.register(SlashCommand(
            "fmt",
            "Форматировать Python файл: /fmt <файл> [--check]",
            fmt_handler,
        ))

        # ── Task 190: /cost ────────────────────────────────────────────────────

        async def cost_handler(arg: str = "", **_: Any) -> str:
            """/cost — подробная разбивка стоимости сессии."""
            if not registry._session:
                return "Сессия не инициализирована."

            tb = registry._session.token_budget
            total_tokens = getattr(tb, "_total_tokens", 0)
            prompt_tokens = getattr(tb, "_total_prompt_tokens", 0)
            completion_tokens = getattr(tb, "_total_completion_tokens", 0)
            total_cost = getattr(tb, "_total_cost_usd", 0.0)
            by_role: dict = getattr(tb, "_by_role", {}) or {}
            model = registry._session.config.llm.default_model

            def _k(n: int) -> str:
                return f"{n / 1000:.1f}k" if n >= 1000 else str(n)

            def _fmt_cost(usd: float) -> str:
                if usd == 0.0:
                    return "$0.000000"
                return f"${usd:.6f}".rstrip("0").rstrip(".")

            lines = ["## Стоимость сессии", ""]
            lines.append(f"**Модель:** `{model}`")
            lines.append("")
            lines.append(f"**Токены ввода:**    {_k(prompt_tokens)}")
            lines.append(f"**Токены вывода:**   {_k(completion_tokens)}")
            lines.append(f"**Итого токенов:**   {_k(total_tokens)}")
            lines.append("")
            lines.append(f"**Стоимость:**       {_fmt_cost(total_cost)}")

            # Per-agent cost estimates (proportional to token usage)
            if by_role and total_tokens > 0:
                lines.append("")
                lines.append("**По агентам:**")
                for role, toks in sorted(by_role.items(), key=lambda x: -x[1]):
                    pct = int(toks / total_tokens * 100)
                    agent_cost = total_cost * toks / total_tokens if total_cost > 0 else 0.0
                    cost_str = f" · {_fmt_cost(agent_cost)}" if total_cost > 0 else ""
                    lines.append(f"  · **{role}**: {_k(toks)} токенов ({pct}%){cost_str}")

            # Session timing summary
            turn_times = registry._turn_times
            if turn_times:
                total_time = sum(turn_times)
                avg_time = total_time / len(turn_times)
                lines.append("")
                lines.append(f"**Ходов:**          {len(turn_times)}")
                lines.append(f"**Время сессии:**   {total_time:.1f}с итого · {avg_time:.1f}с avg")
                if total_cost > 0 and total_time > 0:
                    cost_per_min = total_cost / (total_time / 60)
                    lines.append(f"**$/мин:**          {_fmt_cost(cost_per_min)}")

            lines.append("")
            lines.append("*`/budget` — лимит токенов · `/profile` — по агентам · `/timing` — время*")
            return "\n".join(lines)

        self.register(SlashCommand(
            "cost",
            "Подробная разбивка стоимости сессии",
            cost_handler,
        ))

        # ── Task 191: /reload ──────────────────────────────────────────────────

        async def reload_handler(arg: str = "", **_: Any) -> str:
            """/reload [config|agents|tools] — перезагрузить конфигурацию без перезапуска."""
            if not registry._session:
                return "Сессия не инициализирована."

            target = arg.strip().lower() or "config"
            session = registry._session

            results: list[str] = []

            if target in ("config", "all"):
                try:
                    reloader = getattr(session, "_config_reloader", None)
                    if reloader and hasattr(reloader, "_reload_once"):
                        reloader._reload_once()
                        results.append("✓ Конфигурация перезагружена")
                    elif hasattr(session, "config"):
                        # Re-read config from disk if possible
                        from lidco.core.config import load_config
                        new_cfg = load_config()
                        session.config = new_cfg
                        results.append("✓ Конфигурация перезагружена")
                    else:
                        results.append("⚠ Перезагрузка конфига недоступна (нет reloader)")
                except Exception as exc:
                    results.append(f"✗ Ошибка перезагрузки конфига: {exc}")

            if target in ("agents", "all"):
                try:
                    agent_reg = getattr(session, "agent_registry", None)
                    if agent_reg and hasattr(agent_reg, "reload"):
                        agent_reg.reload()
                        n = len(agent_reg.list_names())
                        results.append(f"✓ Агенты перезагружены ({n} агентов)")
                    else:
                        names = agent_reg.list_names() if agent_reg else []
                        results.append(f"✓ Агенты активны ({len(names)} агентов, горячая перезагрузка недоступна)")
                except Exception as exc:
                    results.append(f"✗ Ошибка перезагрузки агентов: {exc}")

            if target in ("tools", "all"):
                try:
                    tool_reg = getattr(session, "tool_registry", None)
                    if tool_reg and hasattr(tool_reg, "list_tools"):
                        n = len(tool_reg.list_tools())
                        results.append(f"✓ Инструменты активны ({n} инструментов)")
                    else:
                        results.append("⚠ Реестр инструментов недоступен")
                except Exception as exc:
                    results.append(f"✗ Ошибка: {exc}")

            if not results:
                return (
                    f"Неизвестная цель: `{target}`.\n\n"
                    "**Использование:** `/reload [config|agents|tools|all]`"
                )

            model = session.config.llm.default_model
            lines = ["## Перезагрузка", ""]
            lines.extend(results)
            lines.append("")
            lines.append(f"*Модель: `{model}`*")
            return "\n".join(lines)

        self.register(SlashCommand(
            "reload",
            "Перезагрузить конфигурацию: /reload [config|agents|tools|all]",
            reload_handler,
        ))

        # ── Task 192: /inspect ─────────────────────────────────────────────────

        async def inspect_handler(arg: str = "", **_: Any) -> str:
            """/inspect <symbol> — показать исходный код, docstring и сигнатуру символа."""
            import asyncio as _asyncio
            import re as _re
            from pathlib import Path as _Path

            symbol = arg.strip()
            if not symbol:
                return (
                    "**Использование:** `/inspect <символ>`\n\n"
                    "Ищет определение символа в кодовой базе и показывает его.\n\n"
                    "**Примеры:**\n"
                    "  `/inspect CommandRegistry`\n"
                    "  `/inspect process_slash_command`\n"
                    "  `/inspect BaseAgent._run`"
                )

            # Grep for definition
            root = _Path(".")
            if registry._session:
                project_dir = getattr(registry._session, "project_dir", None)
                if project_dir:
                    root = _Path(str(project_dir))

            # Search for def/class definition
            def_pattern = _re.compile(
                rf"^\s*(def|class|async def)\s+{_re.escape(symbol.split('.')[-1])}\b"
            )
            found: list[tuple[str, int]] = []  # (file, lineno)

            for pyf in sorted(root.rglob("*.py")):
                parts = pyf.parts
                if any(p in parts for p in (".git", "__pycache__", ".venv", "venv")):
                    continue
                try:
                    for lineno, line in enumerate(
                        pyf.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
                    ):
                        if def_pattern.search(line):
                            found.append((str(pyf), lineno))
                            if len(found) >= 5:
                                break
                except OSError:
                    pass
                if len(found) >= 5:
                    break

            if not found:
                return f"Символ `{symbol}` не найден в кодовой базе."

            results: list[str] = []
            for file_path, lineno in found[:3]:
                try:
                    source_lines = _Path(file_path).read_text(encoding="utf-8", errors="ignore").splitlines()
                    # Extract up to 40 lines from definition
                    start = lineno - 1
                    end = min(len(source_lines), start + 40)
                    # Trim at next top-level def/class (same indent level)
                    base_indent = len(source_lines[start]) - len(source_lines[start].lstrip())
                    for i in range(start + 1, end):
                        line = source_lines[i]
                        if line.strip() == "":
                            continue
                        indent = len(line) - len(line.lstrip())
                        if indent <= base_indent and _re.match(r"\s*(def|class|async def)\b", line):
                            end = i
                            break
                    excerpt = "\n".join(source_lines[start:end])
                    results.append(
                        f"**`{file_path}:{lineno}`**\n\n```python\n{excerpt}\n```"
                    )
                except OSError:
                    results.append(f"**`{file_path}:{lineno}`** — не удалось прочитать файл")

            header = f"## `{symbol}` — {len(found)} определений" if len(found) > 1 else f"## `{symbol}`"
            if len(found) > 3:
                header += f" (показано 3 из {len(found)})"

            return header + "\n\n" + "\n\n---\n\n".join(results)

        self.register(SlashCommand(
            "inspect",
            "Показать исходный код символа: /inspect <имя>",
            inspect_handler,
        ))

        # ── Task 193: /ask ─────────────────────────────────────────────────────

        async def ask_handler(arg: str = "", **_: Any) -> str:
            """/ask [--model <model>] <question> — быстрый вопрос к LLM без агентского оверхеда."""
            if not registry._session:
                return "Сессия не инициализирована."

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/ask [--model <модель>] <вопрос>`\n\n"
                    "Задаёт быстрый вопрос напрямую LLM без маршрутизации через агентов.\n\n"
                    "**Примеры:**\n"
                    "  `/ask что такое декоратор в Python?`\n"
                    "  `/ask --model openai/gpt-4o-mini explain asyncio`"
                )

            # Parse optional --model flag
            model_override: str | None = None
            _parts = text.split()
            if _parts and _parts[0] == "--model":
                if len(_parts) < 2:
                    return "Укажите имя модели: `/ask --model <модель> <вопрос>`"
                model_override = _parts[1]
                text = " ".join(_parts[2:]).strip()
                if not text:
                    return "Укажите вопрос после флага `--model <модель>`."

            from lidco.llm.base import Message as LLMMessage
            try:
                kwargs: dict = {"temperature": 0.3, "max_tokens": 1000}
                if model_override:
                    kwargs["model"] = model_override

                resp = await registry._session.llm.complete(
                    [LLMMessage(role="user", content=text)],
                    **kwargs,
                )
                answer = (resp.content or "").strip()
                model_used = getattr(resp, "model", model_override or registry._session.config.llm.default_model)
                return f"{answer}\n\n*[{model_used}]*"
            except Exception as exc:
                return f"Ошибка LLM: {exc}"

        self.register(SlashCommand(
            "ask",
            "Быстрый вопрос к LLM напрямую: /ask [--model <модель>] <вопрос>",
            ask_handler,
        ))

        # ── Task 194: /explain ─────────────────────────────────────────────────

        async def explain_handler(arg: str = "", **_: Any) -> str:
            """/explain <code or file> — объяснить код или файл через LLM."""
            if not registry._session:
                return "Сессия не инициализирована."

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/explain <код или путь к файлу>`\n\n"
                    "Объясняет код или содержимое файла простым языком.\n\n"
                    "**Примеры:**\n"
                    "  `/explain src/lidco/core/session.py`\n"
                    "  `/explain lambda x: x**2 if x > 0 else -x`"
                )

            from pathlib import Path as _Path
            from lidco.llm.base import Message as LLMMessage

            # Check if arg looks like a file path
            p = _Path(text)
            source_label = text
            if p.is_file():
                try:
                    code = p.read_text(encoding="utf-8", errors="replace")
                    source_label = str(p)
                    # Trim very large files
                    if len(code) > 8000:
                        code = code[:8000] + "\n... (обрезано)"
                except OSError as exc:
                    return f"Не удалось прочитать `{text}`: {exc}"
            else:
                code = text

            prompt = (
                "Explain the following Python code clearly and concisely in Russian. "
                "Cover: what it does, key patterns used, and any non-obvious parts.\n\n"
                f"```python\n{code}\n```\n\n"
                "Keep the explanation under 300 words."
            )

            try:
                resp = await registry._session.llm.complete(
                    [LLMMessage(role="user", content=prompt)],
                    temperature=0.2,
                    max_tokens=600,
                )
                explanation = (resp.content or "").strip()
            except Exception as exc:
                return f"Ошибка LLM: {exc}"

            return f"## Объяснение: `{source_label}`\n\n{explanation}"

        self.register(SlashCommand(
            "explain",
            "Объяснить код или файл через LLM: /explain <код или файл>",
            explain_handler,
        ))

        # ── Task 195: /token ───────────────────────────────────────────────────

        async def token_handler(arg: str = "", **_: Any) -> str:
            """/token <text> — приблизительный подсчёт токенов для текста."""
            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/token <текст>`\n\n"
                    "Показывает приблизительное количество токенов для текста.\n\n"
                    "**Примеры:**\n"
                    "  `/token def hello(): return 42`\n"
                    "  `/token Привет, как дела?`"
                )

            # Rough tokenization heuristics (no tiktoken required)
            import re as _re

            chars = len(text)
            words = len(text.split())

            # Approximate token count:
            # - ~4 chars per token for English
            # - ~2-3 chars per token for non-ASCII (CJK/Cyrillic)
            # - code has shorter tokens on average
            non_ascii = sum(1 for c in text if ord(c) > 127)
            ascii_chars = chars - non_ascii

            # Mixed estimate
            est_tokens = (ascii_chars // 4) + (non_ascii // 2)
            est_tokens = max(1, est_tokens)

            # Word-based cross-check
            word_est = int(words * 1.3)

            # Use the higher of the two as conservative estimate
            conservative = max(est_tokens, word_est)

            # Cost estimate at common pricing tiers
            _PRICING = {
                "GPT-4o": (2.50, 10.0),       # $/1M in, $/1M out
                "GPT-4o-mini": (0.15, 0.60),
                "Claude Sonnet": (3.0, 15.0),
                "Claude Haiku": (0.25, 1.25),
            }

            lines = [
                "## Подсчёт токенов", "",
                f"**Текст:** {chars} символов · {words} слов",
                f"**Оценка токенов:** ~{conservative}",
                "",
                "**Приблизительная стоимость (per 1K токенов):**",
            ]
            for model_name, (price_in, price_out) in _PRICING.items():
                cost_in = conservative / 1_000_000 * price_in
                cost_out = conservative / 1_000_000 * price_out
                lines.append(
                    f"  · {model_name}: ${cost_in:.6f} вход / ${cost_out:.6f} выход"
                )

            lines.append("")
            lines.append(
                "*Оценка приблизительная (~4 символа/токен для ASCII, "
                "~2 для кириллицы). Точный подсчёт зависит от токенизатора модели.*"
            )
            return "\n".join(lines)

        self.register(SlashCommand(
            "token",
            "Приблизительный подсчёт токенов: /token <текст>",
            token_handler,
        ))

        # ── Task 196: /env ─────────────────────────────────────────────────────

        async def env_handler(arg: str = "", **_: Any) -> str:
            """/env — информация о Python-окружении, пакетах и системе."""
            import sys
            import os
            import platform

            text = arg.strip().lower()

            lines = ["## Окружение", ""]

            # Python
            py_ver = sys.version.split()[0]
            py_impl = platform.python_implementation()
            lines.append(f"**Python:** {py_impl} {py_ver}")
            lines.append(f"**Исполняемый:** `{sys.executable}`")

            # Virtualenv
            venv = os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_DEFAULT_ENV", "")
            if venv:
                lines.append(f"**Virtualenv:** `{venv}`")
            else:
                lines.append("**Virtualenv:** не активен")

            # OS
            lines.append(f"**ОС:** {platform.system()} {platform.release()}")
            lines.append(f"**Архитектура:** {platform.machine()}")

            # CWD
            lines.append(f"**Рабочая директория:** `{os.getcwd()}`")

            # Key packages
            _KEY_PACKAGES = [
                "lidco", "rich", "prompt_toolkit", "litellm", "langchain",
                "langgraph", "pydantic", "pytest", "ruff", "mypy",
            ]
            lines.append("")
            lines.append("**Ключевые пакеты:**")

            import importlib.metadata as _meta
            for pkg in _KEY_PACKAGES:
                try:
                    ver = _meta.version(pkg)
                    lines.append(f"  · `{pkg}` {ver}")
                except _meta.PackageNotFoundError:
                    if text == "all":
                        lines.append(f"  · `{pkg}` — не установлен")

            # Session info
            if registry._session:
                model = registry._session.config.llm.default_model
                lines.append("")
                lines.append(f"**Модель LIDCO:** `{model}`")

            lines.append("")
            lines.append("*`/env all` — показать все пакеты включая неустановленные*")
            return "\n".join(lines)

        self.register(SlashCommand(
            "env",
            "Информация о Python-окружении и пакетах",
            env_handler,
        ))

        # ── Task 197: /bench ───────────────────────────────────────────────────

        async def bench_handler(arg: str = "", **_: Any) -> str:
            """/bench [N] — измерить задержку LLM (N запросов, по умолчанию 3)."""
            import time as _time

            if not registry._session:
                return "Сессия не инициализирована."

            text = arg.strip()
            try:
                n = int(text) if text else 3
                if n < 1:
                    n = 1
                elif n > 10:
                    n = 10
            except ValueError:
                return f"Неверный аргумент `{text}`. Использование: `/bench [N]` (N от 1 до 10)"

            from lidco.llm.base import Message as LLMMessage
            _PROBE = "Reply with exactly: OK"

            latencies: list[float] = []
            errors: list[str] = []
            model = registry._session.config.llm.default_model

            for i in range(n):
                t0 = _time.monotonic()
                try:
                    await registry._session.llm.complete(
                        [LLMMessage(role="user", content=_PROBE)],
                        temperature=0.0,
                        max_tokens=5,
                    )
                    latencies.append(_time.monotonic() - t0)
                except Exception as exc:
                    errors.append(f"Запрос {i + 1}: {exc}")

            if not latencies:
                err_str = "\n".join(errors)
                return f"Все запросы завершились ошибкой:\n\n{err_str}"

            avg = sum(latencies) / len(latencies)
            mn = min(latencies)
            mx = max(latencies)
            total = sum(latencies)

            lines = [f"## Benchmark: `{model}`", ""]
            lines.append(f"**Запросов:** {n} (успешных: {len(latencies)})")
            lines.append(f"**Среднее:** {avg:.2f}с")
            lines.append(f"**Мин / Макс:** {mn:.2f}с / {mx:.2f}с")
            lines.append(f"**Итого:** {total:.2f}с")
            lines.append("")
            lines.append("**По запросам:**")
            for i, lat in enumerate(latencies, 1):
                bar_len = min(20, int(lat / mx * 20)) if mx > 0 else 0
                bar = "█" * bar_len + "░" * (20 - bar_len)
                lines.append(f"  #{i}: {lat:.2f}с  [{bar}]")

            if errors:
                lines.append("")
                lines.append(f"**Ошибки ({len(errors)}):**")
                for e in errors:
                    lines.append(f"  · {e}")

            return "\n".join(lines)

        self.register(SlashCommand(
            "bench",
            "Бенчмарк LLM: измерить задержку N запросами: /bench [N]",
            bench_handler,
        ))

        # ── Task 198: /compare ─────────────────────────────────────────────────

        async def compare_handler(arg: str = "", **_: Any) -> str:
            """/compare <file1> <file2> — сравнить два файла (unified diff + статистика)."""
            import difflib as _diff
            from pathlib import Path as _Path

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/compare <файл1> <файл2>`\n\n"
                    "Показывает unified diff и статистику между двумя файлами.\n\n"
                    "**Пример:** `/compare src/v1.py src/v2.py`"
                )

            parts = text.split()
            if len(parts) < 2:
                return "Укажите два файла: `/compare <файл1> <файл2>`"

            path1, path2 = _Path(parts[0]), _Path(parts[1])

            if not path1.exists():
                return f"Файл не найден: `{parts[0]}`"
            if not path2.exists():
                return f"Файл не найден: `{parts[1]}`"
            if not path1.is_file():
                return f"Это не файл: `{parts[0]}`"
            if not path2.is_file():
                return f"Это не файл: `{parts[1]}`"

            try:
                content1 = path1.read_text(encoding="utf-8", errors="replace")
                content2 = path2.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                return f"Ошибка чтения: {exc}"

            lines1 = content1.splitlines()
            lines2 = content2.splitlines()

            diff = list(_diff.unified_diff(
                lines1, lines2,
                fromfile=str(path1),
                tofile=str(path2),
                lineterm="",
            ))

            # Stats
            added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
            removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
            size1 = path1.stat().st_size
            size2 = path2.stat().st_size

            if not diff:
                return (
                    f"**Файлы идентичны:**\n\n"
                    f"- `{path1}` ({size1} байт, {len(lines1)} строк)\n"
                    f"- `{path2}` ({size2} байт, {len(lines2)} строк)"
                )

            _MAX_DIFF = 200
            truncated = len(diff) > _MAX_DIFF
            diff_text = "\n".join(diff[:_MAX_DIFF])
            if truncated:
                diff_text += f"\n... ({len(diff) - _MAX_DIFF} строк скрыто)"

            stat_lines = [
                f"## Сравнение файлов", "",
                f"**{path1}** ({len(lines1)} строк, {size1} байт)",
                f"**{path2}** ({len(lines2)} строк, {size2} байт)",
                f"",
                f"**+{added}** добавлено / **−{removed}** удалено",
                "",
                f"```diff\n{diff_text}\n```",
            ]
            return "\n".join(stat_lines)

        self.register(SlashCommand(
            "compare",
            "Сравнить два файла: /compare <файл1> <файл2>",
            compare_handler,
        ))

        # ── Task 199: /outline ─────────────────────────────────────────────────

        async def outline_handler(arg: str = "", **_: Any) -> str:
            """/outline [file] — структурный обзор Python файла (классы, функции, сигнатуры)."""
            import re as _re
            from pathlib import Path as _Path

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/outline <файл.py>`\n\n"
                    "Показывает структуру Python-файла: классы, функции и их сигнатуры.\n\n"
                    "**Пример:** `/outline src/lidco/cli/commands.py`"
                )

            p = _Path(text)
            if not p.exists():
                return f"Файл не найден: `{text}`"
            if not p.is_file():
                return f"Это не файл: `{text}`"

            try:
                source = p.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                return f"Не удалось прочитать: {exc}"

            source_lines = source.splitlines()
            total_lines = len(source_lines)

            # Parse structure via regex
            _DEF_RE = _re.compile(
                r"^(?P<indent>\s*)(?P<kind>async def|def|class)\s+(?P<name>\w+)"
                r"(?P<sig>\([^)]*\))?(?:\s*->.*?)?\s*:"
            )

            entries: list[dict] = []
            i = 0
            while i < len(source_lines):
                line = source_lines[i]
                m = _DEF_RE.match(line)
                if m:
                    indent = len(m.group("indent"))
                    kind = m.group("kind").strip()
                    name = m.group("name")
                    sig = m.group("sig") or "()"
                    # Grab docstring if next non-empty line is a triple-quote
                    docstring = ""
                    j = i + 1
                    while j < len(source_lines) and not source_lines[j].strip():
                        j += 1
                    if j < len(source_lines):
                        ds = source_lines[j].strip()
                        if ds.startswith('"""') or ds.startswith("'''"):
                            # Single-line docstring
                            end = ds[3:]
                            if '"""' in end or "'''" in end:
                                docstring = end.split('"""')[0].split("'''")[0].strip()[:80]
                            else:
                                docstring = end.strip()[:80]
                    entries.append({
                        "lineno": i + 1,
                        "indent": indent,
                        "kind": kind,
                        "name": name,
                        "sig": sig if len(sig) <= 60 else sig[:57] + "…)",
                        "docstring": docstring,
                    })
                i += 1

            if not entries:
                return f"`{text}` — нет определений классов или функций ({total_lines} строк)."

            lines = [f"## Структура: `{text}` ({total_lines} строк)", ""]
            for entry in entries:
                prefix = "  " * (entry["indent"] // 4)
                kind_emoji = "🔷" if entry["kind"] == "class" else "⚡" if "async" in entry["kind"] else "🔹"
                sig_str = entry["sig"] if entry["kind"] != "class" else ""
                doc_str = f" — {entry['docstring']}" if entry["docstring"] else ""
                lines.append(
                    f"{prefix}{kind_emoji} **{entry['name']}**`{sig_str}`  "
                    f"`L{entry['lineno']}`{doc_str}"
                )

            lines.append("")
            lines.append(f"*{len(entries)} определений · `/inspect <имя>` — подробнее*")
            return "\n".join(lines)

        self.register(SlashCommand(
            "outline",
            "Структурный обзор Python файла: /outline <файл>",
            outline_handler,
        ))

        # ── Task 200: /tree ────────────────────────────────────────────────────

        async def tree_handler(arg: str = "", **_: Any) -> str:
            """/tree [path] [--depth N] [--py] — показать дерево директорий."""
            from pathlib import Path as _Path
            import re as _re

            text = arg.strip()

            # Parse flags
            depth = 3
            py_only = False
            root_str = "."

            tokens = text.split()
            remaining: list[str] = []
            i = 0
            while i < len(tokens):
                tok = tokens[i]
                if tok == "--depth" and i + 1 < len(tokens):
                    try:
                        depth = max(1, min(10, int(tokens[i + 1])))
                        i += 2
                        continue
                    except ValueError:
                        pass
                elif tok == "--py":
                    py_only = True
                    i += 1
                    continue
                remaining.append(tok)
                i += 1

            if remaining:
                root_str = remaining[0]

            root = _Path(root_str)
            if not root.exists():
                return f"Путь не найден: `{root_str}`"

            _SKIP = frozenset({
                ".git", "__pycache__", ".venv", "venv", "node_modules",
                "dist", "build", ".mypy_cache", ".pytest_cache", ".ruff_cache",
                ".tox", "htmlcov", ".lidco",
            })

            def _render(path: _Path, prefix: str, current_depth: int) -> list[str]:
                if current_depth > depth:
                    return []
                lines: list[str] = []
                try:
                    children = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
                except PermissionError:
                    return []
                # Filter
                visible = []
                for child in children:
                    if child.name.startswith(".") and child.name not in (".env",):
                        continue
                    if child.name in _SKIP:
                        continue
                    if py_only and child.is_file() and not child.name.endswith(".py"):
                        continue
                    visible.append(child)

                for idx, child in enumerate(visible):
                    is_last = idx == len(visible) - 1
                    connector = "└── " if is_last else "├── "
                    extension = "    " if is_last else "│   "
                    if child.is_dir():
                        lines.append(f"{prefix}{connector}**{child.name}/**")
                        lines.extend(_render(child, prefix + extension, current_depth + 1))
                    else:
                        lines.append(f"{prefix}{connector}{child.name}")
                return lines

            header = f"**{root.resolve().name}/**"
            body = _render(root, "", 1)

            if not body:
                return f"{header}\n\n*(пусто)*"

            # Count files and dirs
            total_files = sum(1 for l in body if not l.rstrip().endswith("**"))
            total_dirs = sum(1 for l in body if l.rstrip().endswith("**") or l.rstrip().endswith("*/"))

            lines = [f"## Дерево: `{root_str}`", "", header]
            lines.extend(body)
            lines.append("")
            lines.append(f"*{total_dirs} директорий · {total_files} файлов · глубина {depth}*")
            if depth < 10:
                lines.append(f"*`/tree {root_str} --depth {depth + 2}` — показать глубже*")
            return "\n".join(lines)

        self.register(SlashCommand(
            "tree",
            "Дерево директорий: /tree [путь] [--depth N] [--py]",
            tree_handler,
        ))

        # ── Task 201: /word ────────────────────────────────────────────────────

        async def word_handler(arg: str = "", **_: Any) -> str:
            """/word <file or text> [--top N] — частотный анализ слов."""
            import re as _re
            from pathlib import Path as _Path
            from collections import Counter

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/word <файл или текст> [--top N]`\n\n"
                    "Анализирует частоту слов в файле или тексте.\n\n"
                    "**Примеры:**\n"
                    "  `/word src/lidco/core/session.py`\n"
                    "  `/word The quick brown fox --top 5`"
                )

            # Parse --top flag
            top_n = 20
            top_match = _re.search(r"--top\s+(\d+)", text)
            if top_match:
                top_n = max(1, min(100, int(top_match.group(1))))
                text = text[:top_match.start()].strip() + text[top_match.end():].strip()
                text = text.strip()

            # Try as file path
            source_label = text
            p = _Path(text)
            if p.is_file():
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                    source_label = str(p)
                except OSError as exc:
                    return f"Не удалось прочитать `{text}`: {exc}"
            else:
                content = text

            # Tokenize: extract words (ignore punctuation, numbers)
            words = _re.findall(r"\b[a-zA-Zа-яА-ЯёЁ]{3,}\b", content.lower())

            # Common stop words to exclude
            _STOP = frozenset({
                "and", "the", "for", "that", "this", "with", "from", "are", "was",
                "not", "but", "have", "its", "you", "your", "they", "their",
                "def", "self", "return", "import", "class", "pass", "none",
                "true", "false", "elif", "else", "while", "async", "await",
                "что", "как", "это", "для", "или", "при", "если", "то",
                "не", "да", "нет", "его", "она", "они", "все", "был",
            })
            words = [w for w in words if w not in _STOP]

            if not words:
                return f"В `{source_label}` не найдено слов для анализа."

            counter = Counter(words)
            total = len(words)
            unique = len(counter)
            top = counter.most_common(top_n)

            lines = [f"## Частотный анализ: `{source_label}`", ""]
            lines.append(f"**Слов:** {total} · **Уникальных:** {unique}")
            lines.append("")
            lines.append(f"**Топ {min(top_n, len(top))} слов:**")

            max_count = top[0][1] if top else 1
            for word, count in top:
                pct = int(count / total * 100)
                bar_len = min(15, int(count / max_count * 15))
                bar = "█" * bar_len + "░" * (15 - bar_len)
                lines.append(f"  `{word:<20}` {count:4}×  ({pct}%)  [{bar}]")

            lines.append("")
            lines.append(f"*`/word {source_label} --top 50` — показать больше слов*")
            return "\n".join(lines)

        self.register(SlashCommand(
            "word",
            "Частотный анализ слов в файле: /word <файл> [--top N]",
            word_handler,
        ))

        # ── Task 202: /deps ────────────────────────────────────────────────────

        async def deps_handler(arg: str = "", **_: Any) -> str:
            """/deps <file.py> — граф зависимостей Python файла (импорты)."""
            import re as _re
            from pathlib import Path as _Path

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/deps <файл.py>`\n\n"
                    "Показывает импорты файла и их типы.\n\n"
                    "**Примеры:**\n"
                    "  `/deps src/lidco/core/session.py`\n"
                    "  `/deps src/lidco/cli/app.py`"
                )

            p = _Path(text)
            if not p.exists():
                return f"Файл не найден: `{text}`"
            if not p.is_file():
                return f"Это не файл: `{text}`"
            if not text.endswith(".py") and not p.suffix == ".py":
                return f"Ожидается Python файл (.py): `{text}`"

            try:
                source = p.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                return f"Не удалось прочитать: {exc}"

            # Parse imports
            _IMPORT_RE = _re.compile(
                r"^(?:from\s+([\w.]+)\s+import\s+([\w*,\s]+)|import\s+([\w.,\s]+))",
                _re.MULTILINE,
            )

            stdlib_modules: set[str] = set()
            third_party: set[str] = set()
            local_imports: set[str] = set()

            # Known stdlib top-level names (subset)
            _STDLIB = frozenset({
                "os", "sys", "re", "io", "abc", "ast", "time", "math", "json",
                "enum", "uuid", "copy", "glob", "shutil", "string", "struct",
                "typing", "types", "functools", "itertools", "collections",
                "dataclasses", "contextlib", "threading", "asyncio", "concurrent",
                "subprocess", "pathlib", "datetime", "calendar", "hashlib",
                "base64", "urllib", "http", "email", "csv", "sqlite3",
                "logging", "warnings", "traceback", "inspect", "importlib",
                "platform", "socket", "ssl", "signal", "weakref", "gc",
                "unittest", "textwrap", "difflib", "pprint", "pickle",
                "__future__",
            })

            # Try to get actual project root
            project_root = "."
            if registry._session:
                pd = getattr(registry._session, "project_dir", None)
                if pd:
                    project_root = str(pd)
            project_root_path = _Path(project_root)

            for m in _IMPORT_RE.finditer(source):
                if m.group(1):  # from X import Y
                    module = m.group(1)
                else:  # import X, Y
                    module = (m.group(3) or "").split(",")[0].strip().split(".")[0]

                if not module:
                    continue

                top_level = module.split(".")[0]

                # Check if it's a local module
                possible_local = (
                    project_root_path / module.replace(".", "/")
                ).with_suffix(".py")
                possible_local_pkg = project_root_path / module.replace(".", "/") / "__init__.py"

                if possible_local.exists() or possible_local_pkg.exists():
                    local_imports.add(module)
                elif top_level in _STDLIB or top_level == "_":
                    stdlib_modules.add(module)
                else:
                    third_party.add(module)

            lines = [f"## Зависимости: `{text}`", ""]

            if local_imports:
                lines.append("**Локальные модули:**")
                for imp in sorted(local_imports):
                    lines.append(f"  · `{imp}`")
                lines.append("")

            if third_party:
                lines.append("**Сторонние пакеты:**")
                for imp in sorted(third_party):
                    lines.append(f"  · `{imp}`")
                lines.append("")

            if stdlib_modules:
                lines.append("**Стандартная библиотека:**")
                for imp in sorted(stdlib_modules):
                    lines.append(f"  · `{imp}`")
                lines.append("")

            total = len(local_imports) + len(third_party) + len(stdlib_modules)
            if total == 0:
                return f"`{text}` — нет импортов."

            lines.append(
                f"*{total} импортов: {len(local_imports)} локальных · "
                f"{len(third_party)} сторонних · {len(stdlib_modules)} stdlib*"
            )
            return "\n".join(lines)

        self.register(SlashCommand(
            "deps",
            "Граф зависимостей Python файла: /deps <файл.py>",
            deps_handler,
        ))

        # ── Task 203: /hash ───────────────────────────────────────────────────

        async def hash_handler(arg: str = "", **_) -> str:
            import hashlib

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/hash <текст или файл> [--algo <алгоритм>]`\n\n"
                    "Алгоритмы: `md5`, `sha1`, `sha256` (по умолчанию), `sha512`, `sha3_256`"
                )

            algo = "sha256"
            if "--algo" in text:
                parts = text.split("--algo")
                text = parts[0].strip()
                algo = parts[1].strip().split()[0].lower()

            supported = {"md5", "sha1", "sha256", "sha512", "sha3_256"}
            if algo not in supported:
                return (
                    f"Неизвестный алгоритм `{algo}`. "
                    f"Доступные: {', '.join(sorted(supported))}"
                )

            from pathlib import Path as _Path

            source_label = text
            try:
                p = _Path(text)
                if p.exists() and p.is_file():
                    data = p.read_bytes()
                    source_label = p.name
                else:
                    data = text.encode()
            except Exception:
                data = text.encode()

            h = hashlib.new(algo, data)
            digest = h.hexdigest()

            lines = [f"**Хеш файла/текста:** `{source_label}`", ""]
            lines.append(f"**Алгоритм:** `{algo}`")
            lines.append(f"**Длина дайджеста:** {len(digest)} символов ({len(digest)*4} бит)")
            lines.append("")
            lines.append(f"```\n{digest}\n```")

            # Also show all algos for text input (unless it was a file path with spaces risk)
            if len(data) < 10_000 and source_label == text:
                lines.append("\n**Все алгоритмы:**")
                for a in sorted(supported):
                    lines.append(f"  `{a}`: `{hashlib.new(a, data).hexdigest()}`")

            return "\n".join(lines)

        self.register(SlashCommand(
            "hash",
            "Хеш строки или файла: /hash <текст|файл> [--algo sha256]",
            hash_handler,
        ))

        # ── Task 204: /base64 ─────────────────────────────────────────────────

        async def base64_handler(arg: str = "", **_) -> str:
            import base64 as _b64

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/base64 <текст> [--decode] [--file <путь>]`\n\n"
                    "По умолчанию кодирует текст в Base64. "
                    "С флагом `--decode` — декодирует."
                )

            decode_mode = "--decode" in text
            if decode_mode:
                text = text.replace("--decode", "").strip()

            from pathlib import Path as _Path

            source_label = text[:40] + ("…" if len(text) > 40 else "")

            # Check if it's a file path
            try:
                p = _Path(text)
                if p.exists() and p.is_file():
                    raw = p.read_bytes()
                    source_label = p.name
                    if decode_mode:
                        return (
                            "Декодирование бинарного файла не поддерживается. "
                            "Передайте Base64-строку напрямую."
                        )
                else:
                    raw = text.encode("utf-8")
            except Exception:
                raw = text.encode("utf-8")

            try:
                if decode_mode:
                    # Validate input
                    stripped = text.strip().replace("\n", "").replace(" ", "")
                    decoded = _b64.b64decode(stripped, validate=True)
                    try:
                        result_text = decoded.decode("utf-8")
                        lines = [
                            f"**Base64 → текст** (`{source_label}`)", "",
                            "```",
                            result_text,
                            "```",
                            "",
                            f"*{len(decoded)} байт → {len(result_text)} символов*",
                        ]
                    except UnicodeDecodeError:
                        lines = [
                            f"**Base64 → бинарные данные** (`{source_label}`)", "",
                            f"*{len(decoded)} байт (не UTF-8, бинарный контент)*",
                            "",
                            f"Hex-preview: `{decoded[:32].hex()}`{'…' if len(decoded) > 32 else ''}",
                        ]
                    return "\n".join(lines)
                else:
                    encoded = _b64.b64encode(raw).decode("ascii")
                    # Break into 76-char lines for readability
                    chunks = [encoded[i:i+76] for i in range(0, len(encoded), 76)]
                    lines = [
                        f"**Текст → Base64** (`{source_label}`)", "",
                        "```",
                        "\n".join(chunks),
                        "```",
                        "",
                        f"*{len(raw)} байт → {len(encoded)} символов Base64*",
                    ]
                    return "\n".join(lines)
            except Exception as exc:
                return f"Ошибка: {exc}"

        self.register(SlashCommand(
            "base64",
            "Кодирование/декодирование Base64: /base64 <текст> [--decode]",
            base64_handler,
        ))

        # ── Task 205: /json ───────────────────────────────────────────────────

        async def json_handler(arg: str = "", **_) -> str:
            import json as _json
            from pathlib import Path as _Path

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/json <текст или файл> [--compact] [--keys] [--validate]`\n\n"
                    "Форматирует JSON с отступами, показывает структуру. "
                    "Флаги: `--compact` (минификация), `--keys` (список ключей), "
                    "`--validate` (только проверка)."
                )

            compact = "--compact" in text
            show_keys = "--keys" in text
            validate_only = "--validate" in text

            for flag in ("--compact", "--keys", "--validate"):
                text = text.replace(flag, "").strip()

            source_label = text[:40] + ("…" if len(text) > 40 else "")

            # Try as file path first
            try:
                p = _Path(text)
                if p.exists() and p.is_file():
                    raw = p.read_text(encoding="utf-8")
                    source_label = p.name
                else:
                    raw = text
            except Exception:
                raw = text

            try:
                parsed = _json.loads(raw)
            except _json.JSONDecodeError as exc:
                return (
                    f"**Ошибка JSON** (`{source_label}`)\n\n"
                    f"`{exc}`\n\n"
                    f"*Строка {exc.lineno}, позиция {exc.colno}*"
                )

            if validate_only:
                kind = type(parsed).__name__
                size = len(raw.encode())
                return (
                    f"**JSON валиден** ✓ (`{source_label}`)\n\n"
                    f"Тип: `{kind}` · Размер: {size} байт"
                )

            if compact:
                result = _json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
                lines = [
                    f"**JSON (компакт)** (`{source_label}`)", "",
                    "```json",
                    result[:4000] + ("…" if len(result) > 4000 else ""),
                    "```",
                    "",
                    f"*{len(result)} символов*",
                ]
                return "\n".join(lines)

            formatted = _json.dumps(parsed, indent=2, ensure_ascii=False)

            if show_keys and isinstance(parsed, dict):
                keys = list(parsed.keys())
                lines = [
                    f"**Ключи JSON** (`{source_label}`)", "",
                    f"*{len(keys)} ключей верхнего уровня:*", "",
                ]
                for k in keys:
                    v = parsed[k]
                    vtype = type(v).__name__
                    if isinstance(v, dict):
                        vtype = f"dict ({len(v)} ключей)"
                    elif isinstance(v, list):
                        vtype = f"list ({len(v)} элементов)"
                    lines.append(f"  · `{k}` — *{vtype}*")
                return "\n".join(lines)

            # Default: pretty-print with truncation
            max_lines = 100
            formatted_lines = formatted.splitlines()
            truncated = len(formatted_lines) > max_lines
            display = "\n".join(formatted_lines[:max_lines])

            lines = [
                f"**JSON** (`{source_label}`)", "",
                "```json",
                display,
                "```",
            ]
            if truncated:
                hidden = len(formatted_lines) - max_lines
                lines.append(f"\n*…скрыто {hidden} строк. Используйте `--compact` для минификации.*")

            # Stats
            depth = _json_depth(parsed)
            total_keys = _json_key_count(parsed)
            lines.append(f"\n*Глубина: {depth} · Ключей: {total_keys}*")

            return "\n".join(lines)

        def _json_depth(obj, d=0) -> int:
            if isinstance(obj, dict):
                return max((_json_depth(v, d + 1) for v in obj.values()), default=d + 1)
            if isinstance(obj, list):
                return max((_json_depth(v, d + 1) for v in obj), default=d + 1)
            return d

        def _json_key_count(obj) -> int:
            if isinstance(obj, dict):
                return len(obj) + sum(_json_key_count(v) for v in obj.values())
            if isinstance(obj, list):
                return sum(_json_key_count(v) for v in obj)
            return 0

        self.register(SlashCommand(
            "json",
            "Форматирование и валидация JSON: /json <текст|файл> [--compact|--keys|--validate]",
            json_handler,
        ))

        # ── Task 206: /url ────────────────────────────────────────────────────

        async def url_handler(arg: str = "", **_) -> str:
            from urllib.parse import (
                urlparse, urlencode, parse_qs, quote, unquote, urlunparse,
            )

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/url <url> [--decode] [--encode] [--parse]`\n\n"
                    "По умолчанию парсит URL. "
                    "`--encode` — percent-encode строку, "
                    "`--decode` — декодирует percent-encoded строку, "
                    "`--parse` — разбивает URL на компоненты."
                )

            encode_mode = "--encode" in text
            decode_mode = "--decode" in text
            parse_mode = "--parse" in text

            for flag in ("--encode", "--decode", "--parse"):
                text = text.replace(flag, "").strip()

            if decode_mode:
                decoded = unquote(text)
                return (
                    f"**URL-декодирование**\n\n"
                    f"Вход: `{text}`\n"
                    f"Результат: `{decoded}`"
                )

            if encode_mode:
                encoded = quote(text, safe="")
                return (
                    f"**URL-кодирование**\n\n"
                    f"Вход: `{text}`\n"
                    f"Результат: `{encoded}`"
                )

            # Default: parse URL
            try:
                parsed = urlparse(text)
            except Exception as exc:
                return f"Ошибка разбора URL: {exc}"

            lines = [f"**Разбор URL:** `{text}`", ""]

            if parsed.scheme:
                lines.append(f"**Схема:** `{parsed.scheme}`")
            if parsed.netloc:
                lines.append(f"**Хост:** `{parsed.netloc}`")
            if parsed.path:
                lines.append(f"**Путь:** `{parsed.path}`")
            if parsed.query:
                lines.append(f"**Query-строка:** `{parsed.query}`")
                qs = parse_qs(parsed.query)
                for k, vs in qs.items():
                    lines.append(f"  · `{k}` = `{', '.join(vs)}`")
            if parsed.fragment:
                lines.append(f"**Фрагмент:** `#{parsed.fragment}`")
            if parsed.username:
                lines.append(f"**Пользователь:** `{parsed.username}`")
            if parsed.port:
                lines.append(f"**Порт:** `{parsed.port}`")

            if not any([parsed.scheme, parsed.netloc, parsed.path]):
                return f"Не удалось разобрать URL: `{text}`"

            return "\n".join(lines)

        self.register(SlashCommand(
            "url",
            "Парсинг и кодирование URL: /url <url> [--encode|--decode|--parse]",
            url_handler,
        ))

        # ── Task 207: /uuid ───────────────────────────────────────────────────

        async def uuid_handler(arg: str = "", **_) -> str:
            import uuid as _uuid

            text = arg.strip()

            # Subcommands: validate, info, or generate
            if text.startswith("validate ") or text.startswith("check "):
                raw = text.split(None, 1)[1].strip()
                try:
                    u = _uuid.UUID(raw)
                    ver = u.version if u.variant == _uuid.RFC_4122 else None
                    lines = [
                        f"**UUID валиден** ✓",
                        "",
                        f"**Версия:** {ver if ver else 'не RFC 4122'}",
                        f"**Вариант:** `{u.variant}`",
                        f"**Hex:** `{u.hex}`",
                        f"**Int:** `{u.int}`",
                    ]
                    if ver == 1:
                        lines.append(f"**Время:** `{u.time}`")
                    elif ver == 3 or ver == 5:
                        lines.append("*(хеш-based UUID)*")
                    return "\n".join(lines)
                except ValueError:
                    return f"Неверный UUID: `{raw}`"

            # Generate N UUIDs (default 1, max 20)
            count = 1
            version = 4
            if text:
                parts = text.split()
                for p in parts:
                    if p.isdigit():
                        count = min(int(p), 20)
                    elif p.startswith("v") and p[1:].isdigit():
                        version = int(p[1:])

            generators = {
                1: _uuid.uuid1,
                3: None,  # requires namespace+name
                4: _uuid.uuid4,
                5: None,
            }
            if version not in generators or generators[version] is None:
                version = 4

            gen = generators[version]
            uids = [str(gen()) for _ in range(count)]

            lines = [f"**UUID v{version}** ({count} шт.)", ""]
            lines.extend(f"  `{u}`" for u in uids)
            lines.append("")
            lines.append(f"*Используйте `/uuid validate <uuid>` для проверки*")

            return "\n".join(lines)

        self.register(SlashCommand(
            "uuid",
            "Генерация и проверка UUID: /uuid [N] [v4] | validate <uuid>",
            uuid_handler,
        ))

        # ── Task 208: /calc ───────────────────────────────────────────────────

        async def calc_handler(arg: str = "", **_) -> str:
            import math as _math
            import ast as _ast

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/calc <выражение>`\n\n"
                    "Примеры: `2 + 2`, `sqrt(16)`, `2**10`, `sin(pi/2)`, `log(100, 10)`\n"
                    "Поддерживаются: `+`, `-`, `*`, `/`, `**`, `%`, `//`, "
                    "`sqrt`, `sin`, `cos`, `tan`, `log`, `abs`, `round`, `pi`, `e`"
                )

            # Safe evaluation: whitelist of allowed names
            _SAFE_NAMES = {
                "sqrt": _math.sqrt,
                "sin": _math.sin,
                "cos": _math.cos,
                "tan": _math.tan,
                "log": _math.log,
                "log2": _math.log2,
                "log10": _math.log10,
                "exp": _math.exp,
                "abs": abs,
                "round": round,
                "floor": _math.floor,
                "ceil": _math.ceil,
                "pow": pow,
                "pi": _math.pi,
                "e": _math.e,
                "inf": _math.inf,
                "tau": _math.tau,
            }

            # Validate AST — only allow safe node types
            _ALLOWED_NODES = (
                _ast.Expression, _ast.BinOp, _ast.UnaryOp, _ast.Call,
                _ast.Constant, _ast.Name, _ast.Load,
                _ast.Add, _ast.Sub, _ast.Mult, _ast.Div, _ast.Pow,
                _ast.Mod, _ast.FloorDiv, _ast.USub, _ast.UAdd,
            )

            try:
                tree = _ast.parse(text, mode="eval")
            except SyntaxError:
                return f"Синтаксическая ошибка в выражении: `{text}`"

            for node in _ast.walk(tree):
                if not isinstance(node, _ALLOWED_NODES):
                    return (
                        f"Недопустимая операция в выражении: `{type(node).__name__}`\n"
                        "Разрешены только математические операции."
                    )
                if isinstance(node, _ast.Name) and node.id not in _SAFE_NAMES:
                    return f"Неизвестная переменная или функция: `{node.id}`"
                if isinstance(node, _ast.Call):
                    if not isinstance(node.func, _ast.Name):
                        return "Вызов функции через атрибут не поддерживается."

            try:
                result = eval(compile(tree, "<calc>", "eval"), {"__builtins__": {}}, _SAFE_NAMES)
            except ZeroDivisionError:
                return "Ошибка: деление на ноль."
            except OverflowError:
                return "Ошибка: результат слишком большой."
            except Exception as exc:
                return f"Ошибка вычисления: {exc}"

            # Format result
            if isinstance(result, float):
                if result == int(result) and abs(result) < 1e15:
                    formatted = str(int(result))
                else:
                    formatted = f"{result:.10g}"
            else:
                formatted = str(result)

            lines = [
                f"**Калькулятор**",
                "",
                f"  `{text}` = **{formatted}**",
            ]

            # Show additional info for notable results
            if isinstance(result, (int, float)) and not _math.isinf(result) and not _math.isnan(result):
                if isinstance(result, float) and result != int(result):
                    lines.append(f"\n*Точное значение: {result!r}*")

            return "\n".join(lines)

        self.register(SlashCommand(
            "calc",
            "Математический калькулятор: /calc <выражение>",
            calc_handler,
        ))

        # ── Task 209: /note ───────────────────────────────────────────────────
        # Persistent cross-session notes stored in .lidco/notes.json

        async def note_handler(arg: str = "", **_) -> str:
            import json as _json
            from pathlib import Path as _Path
            import time as _time

            notes_path = _Path(".lidco") / "notes.json"

            def _load() -> list:
                if notes_path.exists():
                    try:
                        return _json.loads(notes_path.read_text(encoding="utf-8"))
                    except Exception:
                        return []
                return []

            def _save(notes: list) -> None:
                notes_path.parent.mkdir(parents=True, exist_ok=True)
                notes_path.write_text(_json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")

            text = arg.strip()

            # list (default with no arg)
            if not text or text in ("list", "ls"):
                notes = _load()
                if not notes:
                    return "Заметок нет. Добавьте: `/note <текст>`"
                lines = [f"**Заметки** ({len(notes)} шт.)", ""]
                for i, n in enumerate(notes, 1):
                    ts = n.get("ts", "")
                    tag = f" `[{n['tag']}]`" if n.get("tag") else ""
                    lines.append(f"**{i}.** {n['text']}{tag}  *{ts}*")
                return "\n".join(lines)

            # del N
            if text.startswith("del ") or text.startswith("delete ") or text.startswith("rm "):
                parts = text.split(None, 1)
                idx_str = parts[1].strip() if len(parts) > 1 else ""
                if not idx_str.isdigit():
                    return "Укажите номер заметки: `/note del <N>`"
                notes = _load()
                idx = int(idx_str) - 1
                if idx < 0 or idx >= len(notes):
                    return f"Заметка #{idx_str} не найдена (всего {len(notes)})."
                removed = notes.pop(idx)
                _save(notes)
                return f"Удалена заметка #{idx_str}: *{removed['text'][:60]}*"

            # clear
            if text == "clear":
                notes = _load()
                count = len(notes)
                _save([])
                return f"Удалено {count} заметок."

            # search <query>
            if text.startswith("search ") or text.startswith("find "):
                query = text.split(None, 1)[1].strip().lower()
                notes = _load()
                matches = [
                    (i + 1, n) for i, n in enumerate(notes)
                    if query in n["text"].lower() or query in n.get("tag", "").lower()
                ]
                if not matches:
                    return f"Заметок по запросу «{query}» не найдено."
                lines = [f"**Найдено заметок:** {len(matches)}", ""]
                for num, n in matches:
                    tag = f" `[{n['tag']}]`" if n.get("tag") else ""
                    lines.append(f"**{num}.** {n['text']}{tag}")
                return "\n".join(lines)

            # tag: "add #bug fix auth" → tag=bug, text=fix auth
            tag = ""
            if text.startswith("#"):
                parts = text.split(None, 1)
                tag = parts[0][1:]
                text = parts[1].strip() if len(parts) > 1 else ""
                if not text:
                    return "Укажите текст заметки после тега: `/note #tag текст`"

            # add <text> (default)
            notes = _load()
            from datetime import datetime as _dt
            ts = _dt.now().strftime("%Y-%m-%d %H:%M")
            notes.append({"text": text, "tag": tag, "ts": ts})
            _save(notes)
            tag_str = f" `[{tag}]`" if tag else ""
            return f"✓ Заметка #{len(notes)} сохранена{tag_str}: *{text[:80]}*"

        self.register(SlashCommand(
            "notes",
            "Постоянные заметки: /notes <текст> | list | del N | search | clear",
            note_handler,
        ))

        # ── Task 210: /git ────────────────────────────────────────────────────
        # Git workflow: log, status, branch, blame

        async def git_handler(arg: str = "", **_) -> str:
            import asyncio as _asyncio
            from pathlib import Path as _Path

            text = arg.strip()

            async def _git(*args, cwd=None, timeout=10) -> tuple[int, str]:
                try:
                    proc = await _asyncio.create_subprocess_exec(
                        "git", *args,
                        stdout=_asyncio.subprocess.PIPE,
                        stderr=_asyncio.subprocess.STDOUT,
                        cwd=cwd,
                    )
                    out, _ = await _asyncio.wait_for(proc.communicate(), timeout=timeout)
                    return proc.returncode or 0, out.decode("utf-8", errors="replace").strip()
                except FileNotFoundError:
                    return 1, "git не найден в PATH."
                except _asyncio.TimeoutError:
                    return 1, "Timeout."
                except Exception as exc:
                    return 1, str(exc)

            if not text or text == "status":
                rc, out = await _git("status", "--short", "--branch")
                if rc != 0:
                    return f"git status ошибка: {out}"
                lines = ["**git status**", ""]
                for line in out.splitlines():
                    if line.startswith("##"):
                        branch_info = line[3:].strip()
                        lines.append(f"**Ветка:** `{branch_info}`")
                    elif line.strip():
                        status_code = line[:2]
                        fname = line[3:]
                        icon = "📝" if "M" in status_code else ("➕" if "A" in status_code else ("🗑" if "D" in status_code else "❓"))
                        lines.append(f"  {icon} `{fname}` *({status_code.strip()})*")
                if len(lines) <= 2:
                    lines.append("*Чисто — нет незафиксированных изменений*")
                return "\n".join(lines)

            if text.startswith("log"):
                parts = text.split()
                n = 10
                for p in parts[1:]:
                    if p.isdigit():
                        n = min(int(p), 50)
                rc, out = await _git("log", f"--oneline", f"-{n}", "--no-color")
                if rc != 0:
                    return f"git log ошибка: {out}"
                if not out:
                    return "История коммитов пуста."
                lines = [f"**git log** (последние {n})", ""]
                for line in out.splitlines():
                    sha, _, msg = line.partition(" ")
                    lines.append(f"  `{sha}` {msg}")
                return "\n".join(lines)

            if text.startswith("branch"):
                rc, out = await _git("branch", "-v", "--no-color")
                if rc != 0:
                    return f"git branch ошибка: {out}"
                lines = ["**git branch**", ""]
                for line in out.splitlines():
                    current = line.startswith("*")
                    marker = "→ " if current else "  "
                    lines.append(f"{marker}`{line.strip()}`")
                return "\n".join(lines)

            if text.startswith("blame"):
                parts = text.split(None, 1)
                if len(parts) < 2:
                    return "Укажите файл: `/git blame <файл> [строки N-M]`"
                rest = parts[1].strip()
                # optional line range: "file.py 10-20"
                toks = rest.rsplit(None, 1)
                file_path = rest
                line_range_args = []
                if len(toks) == 2 and "-" in toks[1] and toks[1].replace("-", "").isdigit():
                    file_path = toks[0]
                    start, end = toks[1].split("-")
                    line_range_args = [f"-L{start},{end}"]
                rc, out = await _git("blame", "--date=short", "--no-color", *line_range_args, file_path)
                if rc != 0:
                    return f"git blame ошибка: {out}"
                lines_out = out.splitlines()[:40]
                if len(out.splitlines()) > 40:
                    lines_out.append(f"*…скрыто {len(out.splitlines()) - 40} строк*")
                return f"**git blame** `{file_path}`\n\n```\n" + "\n".join(lines_out) + "\n```"

            if text.startswith("diff"):
                parts = text.split(None, 1)
                extra = parts[1].strip() if len(parts) > 1 else "HEAD"
                rc, out = await _git("diff", "--no-color", "--stat", extra)
                if rc != 0:
                    return f"git diff ошибка: {out}"
                if not out:
                    return f"Нет изменений (`git diff {extra}`)."
                lines = [f"**git diff** `{extra}`", "", "```", out[:3000], "```"]
                return "\n".join(lines)

            if text.startswith("show"):
                parts = text.split(None, 1)
                ref = parts[1].strip() if len(parts) > 1 else "HEAD"
                rc, out = await _git("show", "--stat", "--no-color", ref)
                if rc != 0:
                    return f"git show ошибка: {out}"
                lines_out = out.splitlines()[:60]
                return f"**git show** `{ref}`\n\n```\n" + "\n".join(lines_out) + "\n```"

            return (
                "**Использование:** `/git <подкоманда>`\n\n"
                "Подкоманды: `status`, `log [N]`, `branch`, `blame <файл> [N-M]`, "
                "`diff [ref]`, `show [ref]`"
            )

        self.register(SlashCommand(
            "git",
            "Git workflow: /git status|log|branch|blame|diff|show",
            git_handler,
        ))

        # ── Task 211: /ctx ────────────────────────────────────────────────────
        # Context window usage meter

        async def ctx_handler(arg: str = "", **_) -> str:
            text = arg.strip()

            # Estimate from session history if available
            history: list = []
            model_name = "unknown"
            if self._session:
                try:
                    orch = getattr(self._session, "_orchestrator", None)
                    if orch:
                        history = getattr(orch, "_messages", []) or []
                    model_name = self._session.config.llm.default_model
                except Exception:
                    pass

            # Rough token estimate: 1 token ≈ 4 chars
            total_chars = sum(len(str(m.get("content", ""))) for m in history)
            estimated_tokens = total_chars // 4

            # Context window sizes by model family
            _CONTEXT_SIZES = {
                "claude-opus-4": 200_000,
                "claude-sonnet-4": 200_000,
                "claude-haiku-4": 200_000,
                "claude-3-5": 200_000,
                "gpt-4o": 128_000,
                "gpt-4-turbo": 128_000,
                "gpt-4": 8_192,
                "gpt-3.5": 16_385,
                "gemini-1.5": 1_000_000,
                "gemini-2": 1_000_000,
            }
            ctx_limit = 200_000  # default Claude
            for key, size in _CONTEXT_SIZES.items():
                if key in model_name:
                    ctx_limit = size
                    break

            used_pct = min(100, (estimated_tokens / ctx_limit) * 100) if ctx_limit else 0
            remaining = max(0, ctx_limit - estimated_tokens)
            remaining_pct = 100 - used_pct

            # Bar chart
            bar_width = 30
            filled = int(bar_width * used_pct / 100)
            if used_pct < 60:
                bar_char = "█"
            elif used_pct < 80:
                bar_char = "▓"
            else:
                bar_char = "▒"
            bar = bar_char * filled + "░" * (bar_width - filled)

            msg_count = len(history)

            lines = [
                "**Контекстное окно**",
                "",
                f"Модель: `{model_name}`",
                f"Лимит: `{ctx_limit:,}` токенов",
                "",
                f"Использовано: `~{estimated_tokens:,}` токенов ({used_pct:.1f}%)",
                f"Осталось:     `~{remaining:,}` токенов ({remaining_pct:.1f}%)",
                f"Сообщений:    `{msg_count}`",
                "",
                f"[{bar}] {used_pct:.0f}%",
            ]

            # Warnings
            if used_pct >= 85:
                lines.append(
                    "\n⚠️  **Контекст почти заполнен.** "
                    "Рассмотрите `/export` + новую сессию или сжатие истории."
                )
            elif used_pct >= 70:
                lines.append(
                    "\n⚡ Использовано >70%. "
                    "Скоро может потребоваться сжатие контекста."
                )
            else:
                lines.append(
                    f"\n*Оценка приблизительная (~4 символа/токен). "
                    f"Осталось ~{remaining // 1000}K токенов.*"
                )

            return "\n".join(lines)

        self.register(SlashCommand(
            "ctx",
            "Состояние контекстного окна и бюджет токенов",
            ctx_handler,
        ))

        # ── Task 212: /regex ──────────────────────────────────────────────────

        async def regex_handler(arg: str = "", **_) -> str:
            import re as _re

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/regex <паттерн> <текст>`\n\n"
                    "Флаги (добавьте после паттерна):\n"
                    "  `--i` — игнорировать регистр\n"
                    "  `--m` — многострочный режим\n"
                    "  `--s` — точка совпадает с `\\n`\n"
                    "  `--all` — показать все совпадения\n\n"
                    "**Примеры:**\n"
                    "  `/regex \\d+ hello world 42`\n"
                    "  `/regex ^def\\s+\\w+ --i --m def Foo(): pass`"
                )

            # Parse flags
            flags = 0
            show_all = False
            for flag in ("--i", "--m", "--s", "--all"):
                if flag in text:
                    text = text.replace(flag, "").strip()
                    if flag == "--i":
                        flags |= _re.IGNORECASE
                    elif flag == "--m":
                        flags |= _re.MULTILINE
                    elif flag == "--s":
                        flags |= _re.DOTALL
                    elif flag == "--all":
                        show_all = True

            # Split pattern from test string: first token is pattern, rest is text
            parts = text.split(None, 1)
            if len(parts) < 2:
                return (
                    "Укажите паттерн и тест-строку: `/regex <паттерн> <текст>`\n\n"
                    f"Получен только: `{text}`"
                )

            pattern, test_str = parts[0], parts[1]

            # Try to compile
            try:
                compiled = _re.compile(pattern, flags)
            except _re.error as exc:
                return (
                    f"**Ошибка паттерна:** `{pattern}`\n\n"
                    f"`{exc}`"
                )

            lines = [f"**Regex:** `{pattern}`", f"**Текст:** `{test_str[:120]}`", ""]

            if show_all:
                matches = list(compiled.finditer(test_str))
                if not matches:
                    lines.append("❌ Совпадений не найдено.")
                else:
                    lines.append(f"✅ **Найдено совпадений: {len(matches)}**")
                    lines.append("")
                    for i, m in enumerate(matches[:20], 1):
                        lines.append(f"**#{i}** `{m.group()}` (позиция {m.start()}–{m.end()})")
                        if m.groups():
                            for j, g in enumerate(m.groups(), 1):
                                lines.append(f"  Группа {j}: `{g}`")
                    if len(matches) > 20:
                        lines.append(f"\n*…ещё {len(matches) - 20} совпадений*")
            else:
                m = compiled.search(test_str)
                if not m:
                    lines.append("❌ Совпадений нет.")
                    # Suggest partial match
                    for length in range(len(pattern), 0, -1):
                        try:
                            partial = _re.compile(pattern[:length], flags)
                            pm = partial.search(test_str)
                            if pm:
                                lines.append(f"\n*Частичное совпадение для `{pattern[:length]}`: `{pm.group()}`*")
                                break
                        except Exception:
                            break
                else:
                    lines.append(f"✅ **Совпадение найдено:** `{m.group()}`")
                    lines.append(f"Позиция: {m.start()}–{m.end()}")
                    if m.groups():
                        lines.append("\n**Группы:**")
                        for i, g in enumerate(m.groups(), 1):
                            lines.append(f"  Группа {i}: `{g}`")
                    if m.groupdict():
                        lines.append("\n**Именованные группы:**")
                        for name, val in m.groupdict().items():
                            lines.append(f"  `{name}`: `{val}`")

                    # Highlight match in context
                    start, end = m.start(), m.end()
                    ctx_start = max(0, start - 20)
                    ctx_end = min(len(test_str), end + 20)
                    prefix = ("…" if ctx_start > 0 else "") + test_str[ctx_start:start]
                    matched = test_str[start:end]
                    suffix = test_str[end:ctx_end] + ("…" if ctx_end < len(test_str) else "")
                    lines.append(f"\nКонтекст: `{prefix}**[{matched}]**{suffix}`")

            return "\n".join(lines)

        self.register(SlashCommand(
            "regex",
            "Тестирование регулярных выражений: /regex <паттерн> <текст> [--i --m --s --all]",
            regex_handler,
        ))

        # ── Task 213: /stat ───────────────────────────────────────────────────

        async def stat_handler(arg: str = "", **_) -> str:
            import os as _os
            import stat as _stat
            from pathlib import Path as _Path
            from datetime import datetime as _dt
            import re as _re

            text = arg.strip()
            if not text:
                return "**Использование:** `/stat <файл или директория>`"

            p = _Path(text)
            if not p.exists():
                return f"Путь не найден: `{text}`"

            st = p.stat()
            size = st.st_size
            mtime = _dt.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            ctime = _dt.fromtimestamp(st.st_ctime).strftime("%Y-%m-%d %H:%M:%S")

            def _fmt_size(n: int) -> str:
                for unit in ("Б", "КБ", "МБ", "ГБ"):
                    if n < 1024:
                        return f"{n:.1f} {unit}"
                    n /= 1024
                return f"{n:.1f} ТБ"

            lines = [f"**Статистика:** `{p.name}`", ""]
            lines.append(f"**Путь:**      `{p.resolve()}`")
            lines.append(f"**Тип:**       {'директория' if p.is_dir() else 'файл'}")
            lines.append(f"**Размер:**    {_fmt_size(size)} ({size:,} байт)")
            lines.append(f"**Изменён:**   {mtime}")
            lines.append(f"**Создан:**    {ctime}")

            # Permissions
            mode = st.st_mode
            perms = _stat.filemode(mode)
            lines.append(f"**Права:**     `{perms}`")

            if p.is_file():
                # Line count and language detection
                try:
                    raw = p.read_bytes()
                    is_binary = b"\x00" in raw[:8192]
                    if not is_binary:
                        content = raw.decode("utf-8", errors="replace")
                        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
                        word_count = len(content.split())
                        char_count = len(content)
                        lines.append(f"**Строк:**     {line_count:,}")
                        lines.append(f"**Слов:**      {word_count:,}")
                        lines.append(f"**Символов:**  {char_count:,}")

                        # Encoding detection hint
                        suffix = p.suffix.lower()
                        lang_map = {
                            ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
                            ".rs": "Rust", ".go": "Go", ".java": "Java",
                            ".cpp": "C++", ".c": "C", ".rb": "Ruby",
                            ".md": "Markdown", ".json": "JSON", ".yaml": "YAML",
                            ".toml": "TOML", ".sh": "Shell", ".sql": "SQL",
                        }
                        if suffix in lang_map:
                            lines.append(f"**Язык:**      {lang_map[suffix]}")
                    else:
                        lines.append("**Тип данных:** бинарный файл")
                except Exception:
                    pass

            elif p.is_dir():
                try:
                    entries = list(p.iterdir())
                    dirs = sum(1 for e in entries if e.is_dir())
                    files = sum(1 for e in entries if e.is_file())
                    lines.append(f"**Содержимое:** {files} файлов, {dirs} директорий")
                    total_size = sum(e.stat().st_size for e in entries if e.is_file())
                    lines.append(f"**Размер содержимого:** {_fmt_size(total_size)}")
                except PermissionError:
                    lines.append("*Нет прав для чтения содержимого*")

            return "\n".join(lines)

        self.register(SlashCommand(
            "stat",
            "Статистика файла или директории: /stat <путь>",
            stat_handler,
        ))

        # ── Task 214: /diff3 ──────────────────────────────────────────────────
        # 3-way merge diff: base, ours, theirs

        async def diff3_handler(arg: str = "", **_) -> str:
            import difflib as _difflib
            from pathlib import Path as _Path

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/diff3 <база> <наш> <их>`\n\n"
                    "Трёхсторонний diff: находит конфликты между двумя версиями "
                    "относительно общей базы.\n\n"
                    "**Пример:** `/diff3 original.py our_version.py their_version.py`"
                )

            parts = text.split()
            if len(parts) < 3:
                return (
                    f"Нужно три файла, получено {len(parts)}.\n"
                    "**Использование:** `/diff3 <база> <наш> <их>`"
                )

            base_path, ours_path, theirs_path = (
                _Path(parts[0]), _Path(parts[1]), _Path(parts[2])
            )

            for label, p in [("база", base_path), ("наш", ours_path), ("их", theirs_path)]:
                if not p.exists():
                    return f"Файл `{label}` не найден: `{p}`"
                if not p.is_file():
                    return f"`{p}` не является файлом."

            base_lines = base_path.read_text(encoding="utf-8", errors="replace").splitlines()
            ours_lines = ours_path.read_text(encoding="utf-8", errors="replace").splitlines()
            theirs_lines = theirs_path.read_text(encoding="utf-8", errors="replace").splitlines()

            # Run merge3 algorithm using difflib SequenceMatcher
            def _merge3(base, ours, theirs):
                """Simple 3-way merge returning (result_lines, conflicts)."""
                result = []
                conflicts = []

                sm_ours = _difflib.SequenceMatcher(None, base, ours)
                sm_theirs = _difflib.SequenceMatcher(None, base, theirs)

                ops_ours = {
                    i: (tag, j1, j2)
                    for tag, i1, i2, j1, j2 in sm_ours.get_opcodes()
                    for i in range(i1, i2)
                    if tag != "equal"
                }
                ops_theirs = {
                    i: (tag, j1, j2)
                    for tag, i1, i2, j1, j2 in sm_theirs.get_opcodes()
                    for i in range(i1, i2)
                    if tag != "equal"
                }

                i = 0
                while i < len(base):
                    in_ours = i in ops_ours
                    in_theirs = i in ops_theirs
                    if not in_ours and not in_theirs:
                        result.append(("equal", base[i]))
                        i += 1
                    elif in_ours and not in_theirs:
                        result.append(("ours", base[i]))
                        i += 1
                    elif not in_ours and in_theirs:
                        result.append(("theirs", base[i]))
                        i += 1
                    else:
                        # Both changed — conflict
                        conflicts.append(i)
                        result.append(("conflict", base[i]))
                        i += 1

                return result, conflicts

            _, conflict_indices = _merge3(base_lines, ours_lines, theirs_lines)

            # Show standard unified-style 3-way diff
            merger = _difflib.Differ()
            diff_ours = list(merger.compare(base_lines, ours_lines))
            diff_theirs = list(merger.compare(base_lines, theirs_lines))

            # Summary stats
            added_ours = sum(1 for l in diff_ours if l.startswith("+ "))
            removed_ours = sum(1 for l in diff_ours if l.startswith("- "))
            added_theirs = sum(1 for l in diff_theirs if l.startswith("+ "))
            removed_theirs = sum(1 for l in diff_theirs if l.startswith("- "))

            lines = [
                "**3-way diff**",
                "",
                f"**База:**  `{base_path.name}`",
                f"**Наш:**   `{ours_path.name}` (+{added_ours} −{removed_ours})",
                f"**Их:**    `{theirs_path.name}` (+{added_theirs} −{removed_theirs})",
                "",
            ]

            if conflict_indices:
                lines.append(f"⚠️  **Конфликты:** {len(conflict_indices)} строк")
            else:
                lines.append("✅ **Конфликтов нет**")

            lines.append("")

            # Show unified diff: ours vs theirs (practical view)
            unified = list(_difflib.unified_diff(
                ours_lines, theirs_lines,
                fromfile=f"наш/{ours_path.name}",
                tofile=f"их/{theirs_path.name}",
                lineterm="",
            ))

            if not unified:
                lines.append("*Наша и их версии идентичны.*")
            else:
                cap = unified[:100]
                lines.append("```diff")
                lines.extend(cap)
                lines.append("```")
                if len(unified) > 100:
                    lines.append(f"\n*…скрыто {len(unified) - 100} строк diff*")

            return "\n".join(lines)

        self.register(SlashCommand(
            "diff3",
            "Трёхсторонний diff: /diff3 <база> <наш> <их>",
            diff3_handler,
        ))

        # ── Task 215: /cat ────────────────────────────────────────────────────

        async def cat_handler(arg: str = "", **_) -> str:
            from pathlib import Path as _Path

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/cat <файл> [N] [N-M] [--num]`\n\n"
                    "Показывает содержимое файла.\n"
                    "  `/cat file.py` — весь файл (до 200 строк)\n"
                    "  `/cat file.py 10` — первые 10 строк\n"
                    "  `/cat file.py 20-40` — строки 20–40\n"
                    "  `/cat file.py --num` — с номерами строк"
                )

            show_nums = "--num" in text
            if show_nums:
                text = text.replace("--num", "").strip()

            # Parse optional line range/count at end
            tokens = text.rsplit(None, 1)
            line_from = 1
            line_to: int | None = None

            if len(tokens) == 2:
                spec = tokens[1]
                if "-" in spec and all(p.isdigit() for p in spec.split("-", 1)):
                    parts = spec.split("-", 1)
                    line_from = max(1, int(parts[0]))
                    line_to = int(parts[1])
                    text = tokens[0].strip()
                elif spec.isdigit():
                    line_to = int(spec)
                    text = tokens[0].strip()

            p = _Path(text)
            if not p.exists():
                return f"Файл не найден: `{text}`"
            if not p.is_file():
                return f"`{text}` — не файл. Для директорий используйте `/tree` или `/ls`."

            try:
                raw = p.read_bytes()
                if b"\x00" in raw[:8192]:
                    size = len(raw)
                    return f"`{p.name}` — бинарный файл ({size:,} байт). Используйте `/stat` для информации."
                content = raw.decode("utf-8", errors="replace")
            except Exception as exc:
                return f"Ошибка чтения файла: {exc}"

            all_lines = content.splitlines()
            total = len(all_lines)

            # Apply range
            lo = line_from - 1          # 0-based
            hi = line_to if line_to else min(lo + 200, total)
            hi = min(hi, total)

            selected = all_lines[lo:hi]
            truncated = hi < total and line_to is None

            # Detect language for code block
            _LANG_MAP = {
                ".py": "python", ".js": "javascript", ".ts": "typescript",
                ".rs": "rust", ".go": "go", ".java": "java", ".cpp": "cpp",
                ".c": "c", ".rb": "ruby", ".sh": "bash", ".md": "markdown",
                ".json": "json", ".yaml": "yaml", ".toml": "toml",
                ".sql": "sql", ".html": "html", ".css": "css",
            }
            lang = _LANG_MAP.get(p.suffix.lower(), "")

            # Format lines
            if show_nums:
                width = len(str(hi))
                body = "\n".join(
                    f"{lo + i + 1:>{width}} │ {line}"
                    for i, line in enumerate(selected)
                )
            else:
                body = "\n".join(selected)

            range_str = f"строки {line_from}–{hi}" if line_from > 1 or line_to else f"строки 1–{hi}"
            header = f"**`{p.name}`** ({range_str} из {total})"

            lines = [header, "", f"```{lang}", body, "```"]
            if truncated:
                lines.append(
                    f"\n*…показано {hi} из {total} строк. "
                    f"Используйте `/cat {p.name} {hi+1}-{min(hi+200, total)}` для продолжения.*"
                )
            return "\n".join(lines)

        self.register(SlashCommand(
            "cat",
            "Просмотр файла: /cat <файл> [N] [N-M] [--num]",
            cat_handler,
        ))

        # ── Task 216: /find ───────────────────────────────────────────────────

        async def find_handler(arg: str = "", **_) -> str:
            import fnmatch as _fnmatch
            from pathlib import Path as _Path

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/find <паттерн> [путь] [--type f|d] [--ext .py]`\n\n"
                    "Поиск файлов по имени.\n"
                    "  `/find *.py` — все .py файлы\n"
                    "  `/find test_* src/` — файлы test_* в src/\n"
                    "  `/find config --type f` — только файлы\n"
                    "  `/find --ext .json` — все JSON файлы"
                )

            # Parse flags
            only_files = False
            only_dirs = False
            ext_filter: str | None = None

            if "--type f" in text:
                only_files = True
                text = text.replace("--type f", "").strip()
            elif "--type d" in text:
                only_dirs = True
                text = text.replace("--type d", "").strip()

            if "--ext" in text:
                parts = text.split("--ext", 1)
                text = parts[0].strip()
                ext_filter = parts[1].strip().split()[0].lower()
                if not ext_filter.startswith("."):
                    ext_filter = "." + ext_filter

            # Split pattern from optional search root
            tokens = text.split()
            pattern = tokens[0] if tokens else "*"
            root_str = tokens[1] if len(tokens) > 1 else "."

            root = _Path(root_str)
            if not root.exists():
                return f"Директория не найдена: `{root_str}`"

            # Skip noise dirs
            _SKIP = {".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache", ".pytest_cache"}

            matches: list[_Path] = []

            def _walk(d: _Path, depth: int = 0) -> None:
                if depth > 10:
                    return
                try:
                    entries = sorted(d.iterdir(), key=lambda e: (e.is_file(), e.name))
                except PermissionError:
                    return
                for entry in entries:
                    if entry.name in _SKIP:
                        continue
                    if only_files and not entry.is_file():
                        pass
                    elif only_dirs and not entry.is_dir():
                        pass
                    else:
                        name_match = _fnmatch.fnmatch(entry.name, pattern) or pattern in entry.name
                        ext_match = (ext_filter is None) or (entry.suffix.lower() == ext_filter)
                        if name_match and ext_match:
                            if (only_files and entry.is_file()) or \
                               (only_dirs and entry.is_dir()) or \
                               (not only_files and not only_dirs):
                                matches.append(entry)
                    if entry.is_dir() and entry.name not in _SKIP:
                        _walk(entry, depth + 1)
                    if len(matches) >= 200:
                        return

            _walk(root)

            if not matches:
                return (
                    f"Файлов по паттерну `{pattern}` не найдено"
                    + (f" в `{root_str}`" if root_str != "." else "") + "."
                )

            lines = [
                f"**Найдено:** {len(matches)} {'(первые 200)' if len(matches) >= 200 else ''}",
                f"**Паттерн:** `{pattern}`"
                + (f"  **Путь:** `{root_str}`" if root_str != "." else ""),
                "",
            ]

            # Group by directory
            by_dir: dict[str, list[_Path]] = {}
            for m in matches[:200]:
                parent = str(m.parent)
                by_dir.setdefault(parent, []).append(m)

            for parent, files in list(by_dir.items())[:30]:
                lines.append(f"**{parent}/**")
                for f in files[:20]:
                    icon = "📁" if f.is_dir() else "📄"
                    size_hint = ""
                    if f.is_file():
                        try:
                            sz = f.stat().st_size
                            size_hint = f" *({sz:,} б)*" if sz < 10_000 else f" *({sz//1024} КБ)*"
                        except Exception:
                            pass
                    lines.append(f"  {icon} `{f.name}`{size_hint}")
                if len(files) > 20:
                    lines.append(f"  *…ещё {len(files) - 20}*")

            return "\n".join(lines)

        self.register(SlashCommand(
            "find",
            "Поиск файлов по имени: /find <паттерн> [путь] [--type f|d] [--ext .py]",
            find_handler,
        ))

        # ── Task 217: /review ─────────────────────────────────────────────────

        async def review_handler(arg: str = "", **_) -> str:
            from pathlib import Path as _Path

            text = arg.strip()

            if not self._session:
                return "Сессия не инициализирована. Запустите LIDCO обычным образом."

            if not text:
                return (
                    "**Использование:** `/review <файл> [--focus <тема>]`\n\n"
                    "AI-ревью кода: баги, проблемы безопасности, качество, предложения.\n\n"
                    "  `/review src/auth.py` — полное ревью\n"
                    "  `/review utils.py --focus security` — фокус на безопасность\n"
                    "  `/review api.py --focus performance` — фокус на производительность"
                )

            focus = ""
            if "--focus" in text:
                parts = text.split("--focus", 1)
                text = parts[0].strip()
                focus = parts[1].strip().split()[0]

            p = _Path(text)
            if not p.exists():
                return f"Файл не найден: `{text}`"
            if not p.is_file():
                return f"`{text}` — не файл."

            try:
                code = p.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                return f"Ошибка чтения: {exc}"

            # Truncate large files
            MAX_CHARS = 8000
            truncated = len(code) > MAX_CHARS
            code_excerpt = code[:MAX_CHARS]
            if truncated:
                code_excerpt += f"\n\n# [обрезано — показано {MAX_CHARS} из {len(code)} символов]"

            focus_instruction = ""
            if focus:
                focus_map = {
                    "security": "Уделите особое внимание уязвимостям безопасности.",
                    "performance": "Уделите особое внимание производительности и узким местам.",
                    "style": "Уделите особое внимание читаемости и стилю кода.",
                    "tests": "Оцените тестируемость кода и покрытие крайних случаев.",
                    "types": "Проверьте аннотации типов и возможные ошибки типизации.",
                }
                focus_instruction = focus_map.get(focus.lower(), f"Уделите особое внимание: {focus}.")

            prompt = (
                f"Проведи код-ревью следующего файла: `{p.name}`.\n\n"
                f"{focus_instruction}\n\n"
                "Структура ответа:\n"
                "1. **Критические проблемы** (баги, уязвимости) — если есть\n"
                "2. **Предупреждения** (потенциальные проблемы, антипаттерны)\n"
                "3. **Предложения** (улучшения кода, читаемость)\n"
                "4. **Итог** (1-2 предложения общей оценки)\n\n"
                f"```python\n{code_excerpt}\n```"
            )

            try:
                resp = await self._session.llm.complete(
                    [{"role": "user", "content": prompt}],
                    temperature=0.2,
                )
                review_text = resp.content
            except Exception as exc:
                return f"Ошибка LLM при ревью: {exc}"

            header = f"**Code Review: `{p.name}`**"
            if focus:
                header += f" *(фокус: {focus})*"
            if truncated:
                header += f"\n*Файл обрезан до {MAX_CHARS} символов*"

            return f"{header}\n\n{review_text}"

        self.register(SlashCommand(
            "review",
            "AI-ревью кода: /review <файл> [--focus security|performance|style]",
            review_handler,
        ))

        # ── Task 218: /test-gen ───────────────────────────────────────────────

        async def test_gen_handler(arg: str = "", **_) -> str:
            from pathlib import Path as _Path

            text = arg.strip()

            if not self._session:
                return "Сессия не инициализирована."

            if not text:
                return (
                    "**Использование:** `/test-gen <файл> [--framework pytest|unittest]`\n\n"
                    "AI-генерация тестов для Python файла.\n\n"
                    "  `/test-gen src/utils.py` — генерация pytest-тестов\n"
                    "  `/test-gen auth.py --framework unittest`"
                )

            framework = "pytest"
            if "--framework" in text:
                parts = text.split("--framework", 1)
                text = parts[0].strip()
                fw_tok = parts[1].strip().split()[0].lower()
                if fw_tok in ("pytest", "unittest"):
                    framework = fw_tok

            p = _Path(text)
            if not p.exists():
                return f"Файл не найден: `{text}`"
            if not p.is_file():
                return f"`{text}` — не файл."
            if p.suffix.lower() != ".py":
                return f"Поддерживаются только Python-файлы (.py), получен `{p.suffix}`."

            try:
                code = p.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                return f"Ошибка чтения: {exc}"

            MAX_CHARS = 6000
            truncated = len(code) > MAX_CHARS
            code_excerpt = code[:MAX_CHARS]
            if truncated:
                code_excerpt += f"\n# [обрезано до {MAX_CHARS} символов]"

            # Determine suggested test file path
            stem = p.stem
            test_filename = f"test_{stem}.py"
            test_dir = "tests/unit/"

            prompt = (
                f"Сгенерируй тесты ({framework}) для следующего Python файла: `{p.name}`.\n\n"
                "Требования:\n"
                f"- Используй фреймворк: {framework}\n"
                "- Покрой все публичные функции и методы классов\n"
                "- Добавь тесты для крайних случаев (пустой ввод, None, граничные значения)\n"
                "- Используй моки (unittest.mock) для внешних зависимостей\n"
                "- Каждый тест должен быть независимым\n"
                "- Добавь docstring к каждому тесту\n\n"
                f"Предложи сохранить в: `{test_dir}{test_filename}`\n\n"
                f"```python\n{code_excerpt}\n```\n\n"
                "Верни только код тестов, без дополнительных объяснений."
            )

            try:
                resp = await self._session.llm.complete(
                    [{"role": "user", "content": prompt}],
                    temperature=0.2,
                )
                tests_code = resp.content
            except Exception as exc:
                return f"Ошибка LLM: {exc}"

            header_lines = [
                f"**Тесты для `{p.name}`** (фреймворк: {framework})",
                f"*Рекомендуемый путь: `{test_dir}{test_filename}`*",
            ]
            if truncated:
                header_lines.append(f"*Файл обрезан до {MAX_CHARS} символов*")

            return "\n".join(header_lines) + "\n\n" + tests_code

        self.register(SlashCommand(
            "test-gen",
            "AI-генерация тестов: /test-gen <файл.py> [--framework pytest|unittest]",
            test_gen_handler,
        ))

        # ── Task 219: /dead ───────────────────────────────────────────────────

        async def dead_handler(arg: str = "", **_) -> str:
            import ast as _ast
            from pathlib import Path as _Path

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/dead <файл.py> [--imports] [--functions] [--all]`\n\n"
                    "Детектор мёртвого кода: неиспользуемые импорты, функции, переменные.\n\n"
                    "  `/dead utils.py` — все категории\n"
                    "  `/dead module.py --imports` — только импорты\n"
                    "  `/dead app.py --functions` — только функции"
                )

            check_imports = "--imports" in text or "--all" in text or (
                "--imports" not in text and "--functions" not in text
            )
            check_functions = "--functions" in text or "--all" in text or (
                "--imports" not in text and "--functions" not in text
            )

            for flag in ("--imports", "--functions", "--all"):
                text = text.replace(flag, "").strip()

            p = _Path(text)
            if not p.exists():
                return f"Файл не найден: `{text}`"
            if not p.is_file():
                return f"`{text}` — не файл."

            try:
                source = p.read_text(encoding="utf-8", errors="replace")
                tree = _ast.parse(source, filename=str(p))
            except SyntaxError as exc:
                return f"Синтаксическая ошибка в `{p.name}`: {exc}"
            except Exception as exc:
                return f"Ошибка чтения: {exc}"

            lines_src = source.splitlines()
            results: list[str] = []

            if check_imports:
                # Collect imported names
                imported: dict[str, int] = {}  # name → line
                for node in _ast.walk(tree):
                    if isinstance(node, _ast.Import):
                        for alias in node.names:
                            name = alias.asname if alias.asname else alias.name.split(".")[0]
                            imported[name] = node.lineno
                    elif isinstance(node, _ast.ImportFrom):
                        for alias in node.names:
                            if alias.name == "*":
                                continue
                            name = alias.asname if alias.asname else alias.name
                            imported[name] = node.lineno

                # Collect all Name usages (excluding import statements)
                used_names: set[str] = set()
                for node in _ast.walk(tree):
                    if isinstance(node, (_ast.Import, _ast.ImportFrom)):
                        continue
                    if isinstance(node, _ast.Name):
                        used_names.add(node.id)
                    elif isinstance(node, _ast.Attribute):
                        if isinstance(node.value, _ast.Name):
                            used_names.add(node.value.id)

                unused_imports = {
                    name: lineno
                    for name, lineno in imported.items()
                    if name not in used_names and name != "_"
                }

                if unused_imports:
                    results.append(f"**Неиспользуемые импорты** ({len(unused_imports)}):")
                    for name, lineno in sorted(unused_imports.items(), key=lambda x: x[1]):
                        results.append(f"  Строка {lineno:>3}: `{name}`")
                else:
                    results.append("✅ **Неиспользуемых импортов нет**")

            if check_functions:
                # Collect defined function/method names
                defined_fns: dict[str, int] = {}
                for node in _ast.walk(tree):
                    if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                        if not node.name.startswith("_") and node.name not in (
                            "main", "setup", "teardown", "setUp", "tearDown"
                        ):
                            defined_fns[node.name] = node.lineno

                # Collect all Call usages
                called: set[str] = set()
                for node in _ast.walk(tree):
                    if isinstance(node, _ast.Call):
                        if isinstance(node.func, _ast.Name):
                            called.add(node.func.id)
                        elif isinstance(node.func, _ast.Attribute):
                            called.add(node.func.attr)

                # Also check string references (decorators, __all__ etc.)
                for node in _ast.walk(tree):
                    if isinstance(node, _ast.Constant) and isinstance(node.value, str):
                        called.add(node.value)

                unused_fns = {
                    name: lineno
                    for name, lineno in defined_fns.items()
                    if name not in called
                }

                if results:
                    results.append("")

                if unused_fns:
                    results.append(f"**Возможно неиспользуемые функции** ({len(unused_fns)}):")
                    results.append("*(не вызываются внутри этого файла — могут использоваться снаружи)*")
                    for name, lineno in sorted(unused_fns.items(), key=lambda x: x[1]):
                        results.append(f"  Строка {lineno:>3}: `def {name}(...)`")
                else:
                    results.append("✅ **Все функции вызываются в файле**")

            header = f"**Анализ мёртвого кода: `{p.name}`**\n"
            return header + "\n".join(results)

        self.register(SlashCommand(
            "dead",
            "Детектор мёртвого кода: /dead <файл.py> [--imports|--functions|--all]",
            dead_handler,
        ))

        # ── Task 220: /standup ────────────────────────────────────────────────

        async def standup_handler(arg: str = "", **_) -> str:
            import asyncio as _asyncio
            from datetime import datetime as _dt, timedelta as _td

            text = arg.strip()
            days = 1
            if text.isdigit():
                days = min(int(text), 30)

            since = (_dt.now() - _td(days=days)).strftime("%Y-%m-%d")

            async def _git(*args, timeout=10) -> tuple[int, str]:
                try:
                    proc = await _asyncio.create_subprocess_exec(
                        "git", *args,
                        stdout=_asyncio.subprocess.PIPE,
                        stderr=_asyncio.subprocess.STDOUT,
                    )
                    out, _ = await _asyncio.wait_for(proc.communicate(), timeout=timeout)
                    return proc.returncode or 0, out.decode("utf-8", errors="replace").strip()
                except Exception as exc:
                    return 1, str(exc)

            # Get commits since N days ago
            rc, commits = await _git(
                "log", f"--since={since}", "--oneline", "--no-color",
                "--format=%h %s"
            )
            # Get changed files
            rc2, files = await _git(
                "diff", "--name-only", f"HEAD~{max(1, days * 3)}..HEAD",
                "--diff-filter=ACMR"
            )
            # Get current branch
            rc3, branch = await _git("rev-parse", "--abbrev-ref", "HEAD")

            from datetime import date as _date
            today = _date.today().strftime("%d %B %Y")

            lines = [f"**Стендап за {today}** (последние {days} дн.)", ""]

            # Branch info
            if rc3 == 0 and branch:
                lines.append(f"**Ветка:** `{branch}`")
                lines.append("")

            # What was done
            lines.append("**Что сделано:**")
            if rc == 0 and commits:
                for line in commits.splitlines()[:15]:
                    sha, _, msg = line.partition(" ")
                    lines.append(f"  · {msg} `[{sha}]`")
            else:
                lines.append("  · Коммитов не найдено")

            lines.append("")

            # Changed files
            if rc2 == 0 and files:
                file_list = files.splitlines()
                lines.append(f"**Изменённые файлы** ({len(file_list)}):")
                for f in file_list[:10]:
                    lines.append(f"  · `{f}`")
                if len(file_list) > 10:
                    lines.append(f"  *…ещё {len(file_list) - 10}*")
            else:
                lines.append("**Изменённые файлы:** не определены")

            lines.append("")
            lines.append("**Блокеры:** —")
            lines.append("**На сегодня:** —")
            lines.append("")
            lines.append("*Заполните блокеры и планы вручную.*")

            return "\n".join(lines)

        self.register(SlashCommand(
            "standup",
            "Авто-стендап из git: /standup [дней=1]",
            standup_handler,
        ))

        # ── Task 221: /pypi ───────────────────────────────────────────────────

        async def pypi_handler(arg: str = "", **_) -> str:
            import json as _json
            import asyncio as _asyncio

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/pypi <пакет> [--versions]`\n\n"
                    "Информация о Python-пакете из PyPI.\n\n"
                    "  `/pypi rich` — последняя версия, описание, ссылки\n"
                    "  `/pypi pydantic --versions` — список версий"
                )

            show_versions = "--versions" in text
            if show_versions:
                text = text.replace("--versions", "").strip()

            package = text.lower().strip()

            # Use pip index info if available, else try PyPI JSON API
            async def _fetch_pypi(pkg: str) -> dict | None:
                try:
                    proc = await _asyncio.create_subprocess_exec(
                        "python", "-m", "pip", "index", "versions", pkg,
                        "--no-color",
                        stdout=_asyncio.subprocess.PIPE,
                        stderr=_asyncio.subprocess.PIPE,
                    )
                    out, err = await _asyncio.wait_for(proc.communicate(), timeout=15)
                    return {"pip_output": out.decode("utf-8", errors="replace").strip()}
                except Exception:
                    return None

            # Try pip show first (for installed packages)
            async def _pip_show(pkg: str) -> str:
                try:
                    proc = await _asyncio.create_subprocess_exec(
                        "python", "-m", "pip", "show", pkg,
                        stdout=_asyncio.subprocess.PIPE,
                        stderr=_asyncio.subprocess.PIPE,
                    )
                    out, _ = await _asyncio.wait_for(proc.communicate(), timeout=10)
                    return out.decode("utf-8", errors="replace").strip()
                except Exception:
                    return ""

            pip_info = await _pip_show(package)

            lines = [f"**PyPI: `{package}`**", ""]

            if pip_info:
                # Parse pip show output
                info: dict[str, str] = {}
                for line in pip_info.splitlines():
                    if ": " in line:
                        key, _, val = line.partition(": ")
                        info[key.strip()] = val.strip()

                if "Name" in info:
                    lines.append(f"**Название:** `{info.get('Name', package)}`")
                if "Version" in info:
                    lines.append(f"**Версия:** `{info.get('Version', '?')}`")
                if "Summary" in info:
                    lines.append(f"**Описание:** {info.get('Summary', '')}")
                if "Author" in info:
                    lines.append(f"**Автор:** {info.get('Author', '')}")
                if "License" in info:
                    lines.append(f"**Лицензия:** `{info.get('License', '')}`")
                if "Location" in info:
                    lines.append(f"**Путь:** `{info.get('Location', '')}`")
                if "Requires" in info and info["Requires"]:
                    requires = info["Requires"]
                    lines.append(f"**Зависимости:** `{requires}`")
                if "Home-page" in info:
                    lines.append(f"**Сайт:** {info.get('Home-page', '')}")
                lines.append("")
                lines.append("✅ *Пакет установлен в текущем окружении*")
            else:
                lines.append(f"⚠️ Пакет `{package}` не установлен локально.")
                lines.append(f"Установить: `pip install {package}`")

            if show_versions:
                versions_data = await _fetch_pypi(package)
                if versions_data and versions_data.get("pip_output"):
                    lines.append("")
                    lines.append("**Доступные версии:**")
                    lines.append(f"```\n{versions_data['pip_output'][:1000]}\n```")

            return "\n".join(lines)

        self.register(SlashCommand(
            "pypi",
            "Информация о Python-пакете: /pypi <пакет> [--versions]",
            pypi_handler,
        ))

        # ── Task 222: /head ───────────────────────────────────────────────────

        async def head_handler(arg: str = "", **_) -> str:
            from pathlib import Path as _Path

            text = arg.strip()
            if not text:
                return "**Использование:** `/head <файл> [N=10]`\n\nПоказывает первые N строк файла."

            tokens = text.rsplit(None, 1)
            n = 10
            if len(tokens) == 2 and tokens[1].isdigit():
                n = min(int(tokens[1]), 500)
                text = tokens[0].strip()

            p = _Path(text)
            if not p.exists():
                return f"Файл не найден: `{text}`"
            if not p.is_file():
                return f"`{text}` — не файл."

            try:
                raw = p.read_bytes()
                if b"\x00" in raw[:8192]:
                    return f"`{p.name}` — бинарный файл."
                lines = raw.decode("utf-8", errors="replace").splitlines()
            except Exception as exc:
                return f"Ошибка чтения: {exc}"

            selected = lines[:n]
            total = len(lines)

            from pathlib import Path as _P
            _LANG_MAP = {
                ".py": "python", ".js": "javascript", ".ts": "typescript",
                ".sh": "bash", ".json": "json", ".yaml": "yaml",
                ".toml": "toml", ".md": "markdown", ".sql": "sql",
            }
            lang = _LANG_MAP.get(p.suffix.lower(), "")

            header = f"**`{p.name}`** (первые {len(selected)} из {total} строк)"
            body = "\n".join(selected)
            result = f"{header}\n\n```{lang}\n{body}\n```"
            if total > n:
                result += f"\n*…ещё {total - n} строк. Используйте `/cat {p.name} {n+1}-{min(n*2, total)}`*"
            return result

        self.register(SlashCommand(
            "head",
            "Первые N строк файла: /head <файл> [N=10]",
            head_handler,
        ))

        # ── Task 223: /tail ───────────────────────────────────────────────────

        async def tail_handler(arg: str = "", **_) -> str:
            from pathlib import Path as _Path

            text = arg.strip()
            if not text:
                return "**Использование:** `/tail <файл> [N=10]`\n\nПоказывает последние N строк файла."

            tokens = text.rsplit(None, 1)
            n = 10
            if len(tokens) == 2 and tokens[1].isdigit():
                n = min(int(tokens[1]), 500)
                text = tokens[0].strip()

            p = _Path(text)
            if not p.exists():
                return f"Файл не найден: `{text}`"
            if not p.is_file():
                return f"`{text}` — не файл."

            try:
                raw = p.read_bytes()
                if b"\x00" in raw[:8192]:
                    return f"`{p.name}` — бинарный файл."
                lines = raw.decode("utf-8", errors="replace").splitlines()
            except Exception as exc:
                return f"Ошибка чтения: {exc}"

            total = len(lines)
            selected = lines[-n:] if n <= total else lines
            start_line = max(1, total - n + 1)

            _LANG_MAP = {
                ".py": "python", ".js": "javascript", ".ts": "typescript",
                ".sh": "bash", ".json": "json", ".yaml": "yaml",
                ".toml": "toml", ".md": "markdown", ".sql": "sql",
            }
            lang = _LANG_MAP.get(p.suffix.lower(), "")

            header = f"**`{p.name}`** (строки {start_line}–{total} из {total})"
            body = "\n".join(selected)
            result = f"{header}\n\n```{lang}\n{body}\n```"
            if total > n:
                result += f"\n*Используйте `/cat {p.name}` для полного просмотра*"
            return result

        self.register(SlashCommand(
            "tail",
            "Последние N строк файла: /tail <файл> [N=10]",
            tail_handler,
        ))

        # ── Task 224: /cd and /ls ─────────────────────────────────────────────

        async def cd_handler(arg: str = "", **_) -> str:
            import os as _os
            from pathlib import Path as _Path

            text = arg.strip()
            if not text or text == "~":
                target = _Path.home()
            elif text == "-":
                # Go to previous dir (store in registry attr)
                prev = getattr(self, "_prev_dir", None)
                if prev is None:
                    return "Предыдущая директория неизвестна."
                target = _Path(prev)
            elif text == "..":
                target = _Path.cwd().parent
            else:
                target = _Path(text).expanduser()

            if not target.exists():
                return f"Директория не найдена: `{text}`"
            if not target.is_dir():
                return f"`{text}` — не директория."

            prev = str(_Path.cwd())
            try:
                _os.chdir(target)
                self._prev_dir = prev
                cwd = _Path.cwd()
                # Count files/dirs for context
                try:
                    entries = list(cwd.iterdir())
                    nfiles = sum(1 for e in entries if e.is_file())
                    ndirs = sum(1 for e in entries if e.is_dir())
                    hint = f"*{nfiles} файлов, {ndirs} директорий*"
                except Exception:
                    hint = ""
                return f"✓ `{cwd}`\n{hint}"
            except PermissionError:
                return f"Нет прав для перехода в `{target}`."

        self.register(SlashCommand(
            "cd",
            "Смена рабочей директории: /cd <путь> | .. | ~ | -",
            cd_handler,
        ))

        async def ls_handler(arg: str = "", **_) -> str:
            from pathlib import Path as _Path

            text = arg.strip()
            long_mode = "--l" in text or "-l" in text
            show_all = "--all" in text or "-a" in text
            for flag in ("--l", "-l", "--all", "-a"):
                text = text.replace(flag, "").strip()

            target = _Path(text) if text else _Path.cwd()
            if not target.exists():
                return f"Не найдено: `{text}`"
            if not target.is_dir():
                return f"`{text}` — не директория."

            _SKIP = {"__pycache__", ".mypy_cache", ".pytest_cache"}

            try:
                entries = sorted(target.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
            except PermissionError:
                return f"Нет прав для чтения `{target}`."

            if not show_all:
                entries = [e for e in entries if not e.name.startswith(".") and e.name not in _SKIP]

            if not entries:
                return f"`{target}` — пусто."

            lines = [f"**`{target}/`** ({len(entries)} элементов)", ""]

            if long_mode:
                from datetime import datetime as _dt
                for e in entries:
                    try:
                        st = e.stat()
                        size = st.st_size
                        mtime = _dt.fromtimestamp(st.st_mtime).strftime("%m-%d %H:%M")
                        icon = "📁" if e.is_dir() else "📄"
                        if size < 1024:
                            size_str = f"{size}Б"
                        elif size < 1_048_576:
                            size_str = f"{size//1024}КБ"
                        else:
                            size_str = f"{size//1_048_576}МБ"
                        lines.append(f"{icon} `{e.name:<30}` {size_str:>8}  {mtime}")
                    except Exception:
                        lines.append(f"  `{e.name}`")
            else:
                # Compact grid: dirs first, then files
                dirs = [e for e in entries if e.is_dir()]
                files = [e for e in entries if e.is_file()]
                if dirs:
                    lines.append("**Директории:**  " + "  ".join(f"`{d.name}/`" for d in dirs))
                if files:
                    # Group by extension
                    from collections import defaultdict as _dd
                    by_ext: dict = _dd(list)
                    for f in files:
                        by_ext[f.suffix or "(без расш.)"].append(f.name)
                    for ext, names in sorted(by_ext.items()):
                        lines.append(f"**{ext}:**  " + "  ".join(f"`{n}`" for n in names[:20]))

            lines.append(f"\n*`{target}`*")
            return "\n".join(lines)

        self.register(SlashCommand(
            "ls",
            "Список файлов: /ls [путь] [--l] [--all]",
            ls_handler,
        ))

        # ── Task 225: /macro ──────────────────────────────────────────────────
        # Record and replay sequences of slash commands

        self._macros: dict[str, list[str]] = {}
        self._macro_recording: str | None = None
        self._macro_buffer: list[str] = []

        async def macro_handler(arg: str = "", **_) -> str:
            text = arg.strip()

            if not text or text == "list":
                if not self._macros:
                    return "Макросов нет. Создайте: `/macro record <имя>`"
                lines = [f"**Макросы** ({len(self._macros)} шт.)", ""]
                for name, cmds in self._macros.items():
                    lines.append(f"  **{name}** — {len(cmds)} команд: {', '.join(f'`{c}`' for c in cmds[:3])}" +
                                 ("…" if len(cmds) > 3 else ""))
                return "\n".join(lines)

            parts = text.split(None, 1)
            subcmd = parts[0].lower()
            rest = parts[1].strip() if len(parts) > 1 else ""

            if subcmd == "record":
                if not rest:
                    return "Укажите имя макроса: `/macro record <имя>`"
                if self._macro_recording:
                    return (f"Уже записывается макрос `{self._macro_recording}`. "
                            "Завершите: `/macro stop`")
                self._macro_recording = rest
                self._macro_buffer = []
                return f"⏺ Запись макроса `{rest}` начата. Вводите команды, затем `/macro stop`."

            if subcmd == "stop":
                if not self._macro_recording:
                    return "Нет активной записи."
                name = self._macro_recording
                self._macros[name] = list(self._macro_buffer)
                count = len(self._macro_buffer)
                self._macro_recording = None
                self._macro_buffer = []
                return f"⏹ Макрос `{name}` сохранён ({count} команд)."

            if subcmd == "add":
                if not self._macro_recording:
                    return "Запись не активна. Начните: `/macro record <имя>`"
                if not rest:
                    return "Укажите команду: `/macro add <команда>`"
                self._macro_buffer.append(rest)
                return f"✓ Добавлено в `{self._macro_recording}` [#{len(self._macro_buffer)}]: `{rest}`"

            if subcmd == "play":
                if not rest:
                    return "Укажите имя макроса: `/macro play <имя>`"
                if rest not in self._macros:
                    available = ", ".join(self._macros.keys()) or "нет"
                    return f"Макрос `{rest}` не найден. Доступные: {available}"
                cmds = self._macros[rest]
                lines = [f"**Воспроизведение макроса `{rest}`** ({len(cmds)} команд)", ""]
                for i, cmd in enumerate(cmds, 1):
                    lines.append(f"  {i}. `{cmd}`")
                lines.append(
                    f"\n*Для выполнения команд используйте их напрямую "
                    f"или `/run` для shell-команд.*"
                )
                return "\n".join(lines)

            if subcmd == "del" or subcmd == "delete":
                if not rest:
                    return "Укажите имя: `/macro del <имя>`"
                if rest not in self._macros:
                    return f"Макрос `{rest}` не найден."
                del self._macros[rest]
                return f"Макрос `{rest}` удалён."

            if subcmd == "show":
                if not rest:
                    return "Укажите имя: `/macro show <имя>`"
                if rest not in self._macros:
                    return f"Макрос `{rest}` не найден."
                cmds = self._macros[rest]
                lines = [f"**Макрос `{rest}`** ({len(cmds)} команд)", ""]
                for i, cmd in enumerate(cmds, 1):
                    lines.append(f"  {i}. `/{cmd}`")
                return "\n".join(lines)

            if subcmd == "clear":
                count = len(self._macros)
                self._macros.clear()
                return f"Удалено {count} макросов."

            return (
                "**Использование:** `/macro <подкоманда>`\n\n"
                "  `record <имя>` — начать запись\n"
                "  `add <команда>` — добавить команду в запись\n"
                "  `stop` — завершить запись\n"
                "  `play <имя>` — показать шаги макроса\n"
                "  `show <имя>` — просмотр команд\n"
                "  `del <имя>` — удалить макрос\n"
                "  `list` — все макросы\n"
                "  `clear` — удалить все"
            )

        self.register(SlashCommand(
            "macro",
            "Макросы команд: /macro record|stop|add|play|show|del|list|clear",
            macro_handler,
        ))

        # ── Task 226: /coverage ───────────────────────────────────────────────

        async def coverage_handler(arg: str = "", **_) -> str:
            import asyncio as _asyncio
            import json as _json
            from pathlib import Path as _Path

            text = arg.strip()
            show_missing = "--missing" in text or "--m" in text
            for flag in ("--missing", "--m"):
                text = text.replace(flag, "").strip()

            target = text or "."

            # Try reading existing .coverage / coverage.json first
            cov_json = _Path(".coverage.json")
            cov_xml = _Path("coverage.xml")

            # Run pytest --cov if no existing report
            async def _run_coverage(path: str) -> tuple[int, str]:
                try:
                    proc = await _asyncio.create_subprocess_exec(
                        "python", "-m", "pytest", path,
                        "--cov=" + path,
                        "--cov-report=term-missing",
                        "--cov-report=json:.coverage.json",
                        "-q", "--no-header", "--tb=no",
                        stdout=_asyncio.subprocess.PIPE,
                        stderr=_asyncio.subprocess.STDOUT,
                    )
                    out, _ = await _asyncio.wait_for(proc.communicate(), timeout=60)
                    return proc.returncode or 0, out.decode("utf-8", errors="replace")
                except _asyncio.TimeoutError:
                    return 1, "Timeout (60s)"
                except FileNotFoundError:
                    return 1, "pytest не найден."
                except Exception as exc:
                    return 1, str(exc)

            lines = [f"**Coverage** `{target}`", ""]

            # Try reading existing JSON report
            if cov_json.exists():
                try:
                    data = _json.loads(cov_json.read_text())
                    totals = data.get("totals", {})
                    pct = totals.get("percent_covered", 0)
                    covered = totals.get("covered_lines", 0)
                    missing = totals.get("missing_lines", 0)
                    total_stmts = totals.get("num_statements", 0)

                    # Bar
                    bar_w = 25
                    filled = int(bar_w * pct / 100)
                    color_char = "█" if pct >= 80 else ("▓" if pct >= 60 else "░")
                    bar = color_char * filled + "░" * (bar_w - filled)

                    lines.append(f"[{bar}] **{pct:.1f}%**")
                    lines.append("")
                    lines.append(f"Покрыто:  `{covered}` / `{total_stmts}` строк")
                    lines.append(f"Пропущено: `{missing}` строк")
                    lines.append("")

                    # Per-file breakdown
                    files_data = data.get("files", {})
                    if files_data:
                        lines.append("**По файлам:**")
                        sorted_files = sorted(
                            files_data.items(),
                            key=lambda x: x[1].get("summary", {}).get("percent_covered", 100),
                        )
                        for fname, fdata in sorted_files[:20]:
                            summary = fdata.get("summary", {})
                            fpct = summary.get("percent_covered", 0)
                            fmissing = summary.get("missing_lines", 0)
                            icon = "✅" if fpct >= 80 else ("⚠️" if fpct >= 60 else "❌")
                            short = _Path(fname).name
                            miss_str = f" (пропущено: {fdata.get('missing_lines', [][:5])})" if show_missing and fmissing else ""
                            lines.append(f"  {icon} `{short:<30}` {fpct:>5.1f}%{miss_str}")

                    lines.append(f"\n*Из кэша `.coverage.json`. Запустите тесты для обновления.*")
                    return "\n".join(lines)
                except Exception:
                    pass

            # No existing report — run coverage
            lines.append("Запускаю тесты с coverage…")
            rc, output = await _run_coverage(target)

            # Try to parse JSON after run
            if cov_json.exists():
                try:
                    data = _json.loads(cov_json.read_text())
                    totals = data.get("totals", {})
                    pct = totals.get("percent_covered", 0)
                    lines = [f"**Coverage** `{target}`", "", f"**Итого: {pct:.1f}%**", ""]
                    lines.append("```")
                    for line in output.splitlines()[-30:]:
                        lines.append(line)
                    lines.append("```")
                    return "\n".join(lines)
                except Exception:
                    pass

            # Fallback: show raw output
            out_lines = output.splitlines()[-40:]
            lines.extend(["```"] + out_lines + ["```"])
            if rc != 0:
                lines.append(f"\n*Exit code: {rc}*")
            return "\n".join(lines)

        self.register(SlashCommand(
            "coverage",
            "Отчёт покрытия тестами: /coverage [путь] [--missing]",
            coverage_handler,
        ))

        # ── Task 227: /complexity ─────────────────────────────────────────────

        async def complexity_handler(arg: str = "", **_) -> str:
            import ast as _ast
            from pathlib import Path as _Path

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/complexity <файл.py> [--top N]`\n\n"
                    "Цикломатическая сложность функций файла.\n\n"
                    "  `/complexity src/utils.py` — все функции\n"
                    "  `/complexity module.py --top 5` — топ-5 сложных"
                )

            top_n = 0
            if "--top" in text:
                parts = text.split("--top", 1)
                text = parts[0].strip()
                tok = parts[1].strip().split()[0]
                if tok.isdigit():
                    top_n = int(tok)

            p = _Path(text)
            if not p.exists():
                return f"Файл не найден: `{text}`"
            if not p.is_file():
                return f"`{text}` — не файл."

            try:
                source = p.read_text(encoding="utf-8", errors="replace")
                tree = _ast.parse(source, filename=str(p))
            except SyntaxError as exc:
                return f"Синтаксическая ошибка: {exc}"
            except Exception as exc:
                return f"Ошибка чтения: {exc}"

            def _cyclomatic(node) -> int:
                """Count decision points: if/elif/for/while/except/with/assert/bool ops."""
                count = 1  # base complexity
                for child in _ast.walk(node):
                    if isinstance(child, (
                        _ast.If, _ast.For, _ast.While, _ast.ExceptHandler,
                        _ast.With, _ast.Assert, _ast.comprehension,
                    )):
                        count += 1
                    elif isinstance(child, _ast.BoolOp):
                        count += len(child.values) - 1
                return count

            results: list[tuple[int, str, int, str]] = []  # (complexity, name, lineno, kind)

            for node in _ast.walk(tree):
                if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                    cc = _cyclomatic(node)
                    kind = "async def" if isinstance(node, _ast.AsyncFunctionDef) else "def"
                    results.append((cc, node.name, node.lineno, kind))
                elif isinstance(node, _ast.ClassDef):
                    # Count class-level complexity (methods)
                    class_methods = [
                        n for n in _ast.walk(node)
                        if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef))
                    ]
                    if not class_methods:
                        results.append((1, node.name, node.lineno, "class"))

            if not results:
                return f"`{p.name}` — нет функций или классов для анализа."

            results.sort(key=lambda x: -x[0])
            if top_n:
                results = results[:top_n]

            total = len(results)
            avg = sum(r[0] for r in results) / total if total else 0
            max_cc = results[0][0] if results else 0

            def _label(cc: int) -> str:
                if cc <= 5:
                    return "✅ просто"
                elif cc <= 10:
                    return "⚠️ умеренно"
                elif cc <= 20:
                    return "🔶 сложно"
                else:
                    return "❌ очень сложно"

            lines = [
                f"**Цикломатическая сложность: `{p.name}`**",
                "",
                f"Функций: {total} · Средняя: {avg:.1f} · Максимум: {max_cc}",
                "",
                f"{'Сложность':>10}  {'Функция':<30}  {'Строка':>6}  Оценка",
                "─" * 65,
            ]

            for cc, name, lineno, kind in results:
                label = _label(cc)
                lines.append(f"{cc:>10}  `{kind} {name}`{'':.<{max(0, 28-len(name)-len(kind)-1)}}  L{lineno:<5}  {label}")

            lines.append("")
            lines.append(f"*Рекомендуется: CC ≤ 10. Рефакторинг при CC > 10.*")
            return "\n".join(lines)

        self.register(SlashCommand(
            "complexity",
            "Цикломатическая сложность: /complexity <файл.py> [--top N]",
            complexity_handler,
        ))

        # ── Task 228: /docstring ──────────────────────────────────────────────

        async def docstring_handler(arg: str = "", **_) -> str:
            import ast as _ast
            from pathlib import Path as _Path

            text = arg.strip()

            if not self._session:
                return "Сессия не инициализирована."

            if not text:
                return (
                    "**Использование:** `/docstring <файл.py> [<функция>]`\n\n"
                    "AI-генерация docstrings для функций и классов.\n\n"
                    "  `/docstring utils.py` — для всех публичных функций\n"
                    "  `/docstring utils.py parse_config` — для конкретной функции"
                )

            # Split file from optional function name
            tokens = text.split()
            file_path_str = tokens[0]
            target_fn = tokens[1] if len(tokens) > 1 else None

            p = _Path(file_path_str)
            if not p.exists():
                return f"Файл не найден: `{file_path_str}`"
            if not p.is_file():
                return f"`{file_path_str}` — не файл."
            if p.suffix.lower() != ".py":
                return f"Только Python-файлы (.py), получен `{p.suffix}`."

            try:
                source = p.read_text(encoding="utf-8", errors="replace")
                tree = _ast.parse(source)
            except SyntaxError as exc:
                return f"Синтаксическая ошибка: {exc}"

            source_lines = source.splitlines()

            def _get_snippet(node) -> str:
                start = node.lineno - 1
                end = min(start + 30, len(source_lines))
                return "\n".join(source_lines[start:end])

            # Find functions/classes to document
            targets: list[tuple[str, str, int]] = []  # (name, snippet, lineno)
            for node in _ast.walk(tree):
                if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
                    if node.name.startswith("_"):
                        continue
                    if target_fn and node.name != target_fn:
                        continue
                    # Check if already has docstring
                    has_doc = (
                        isinstance(node.body[0], _ast.Expr)
                        and isinstance(node.body[0].value, _ast.Constant)
                        and isinstance(node.body[0].value.value, str)
                    ) if node.body else False
                    if not has_doc:
                        targets.append((node.name, _get_snippet(node), node.lineno))

            if not targets:
                if target_fn:
                    return f"Функция `{target_fn}` не найдена или уже имеет docstring."
                return f"✅ Все публичные функции в `{p.name}` уже имеют docstrings."

            # Limit to 5 at a time
            cap = targets[:5]
            if len(targets) > 5:
                note = f"\n*Показаны первые 5 из {len(targets)} функций без docstring.*"
            else:
                note = ""

            snippets = "\n\n".join(
                f"### `{name}` (строка {lineno})\n```python\n{snippet}\n```"
                for name, snippet, lineno in cap
            )

            prompt = (
                f"Сгенерируй docstrings в Google-стиле для следующих Python функций из `{p.name}`.\n\n"
                "Формат для каждой:\n"
                "```\n"
                "Функция: <имя>\n"
                '"""\n'
                "Краткое описание.\n\n"
                "Args:\n"
                "    param: описание\n\n"
                "Returns:\n"
                "    описание возвращаемого значения\n\n"
                "Raises:\n"
                "    ExceptionType: когда возникает\n"
                '"""\n'
                "```\n\n"
                f"{snippets}"
            )

            try:
                resp = await self._session.llm.complete(
                    [{"role": "user", "content": prompt}],
                    temperature=0.2,
                )
                docstrings = resp.content
            except Exception as exc:
                return f"Ошибка LLM: {exc}"

            header = (
                f"**Docstrings для `{p.name}`**"
                + (f" → `{target_fn}`" if target_fn else f" ({len(cap)} функций)")
            )
            return f"{header}\n\n{docstrings}{note}"

        self.register(SlashCommand(
            "docstring",
            "AI-генерация docstrings: /docstring <файл.py> [функция]",
            docstring_handler,
        ))

        # ── Task 229: /security-scan ──────────────────────────────────────────

        async def security_scan_handler(arg: str = "", **_) -> str:
            import re as _re
            from pathlib import Path as _Path

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/security-scan <файл.py или директория>`\n\n"
                    "Сканирует Python-код на типичные уязвимости:\n"
                    "  · Захардкоженные секреты (пароли, API-ключи, токены)\n"
                    "  · SQL-инъекции (f-строки в SQL-запросах)\n"
                    "  · Использование `eval`, `exec`, `pickle`\n"
                    "  · `subprocess` с `shell=True`\n"
                    "  · Небезопасная десериализация\n"
                    "  · Отладочные маркеры в production-коде"
                )

            # Security patterns: (regex, severity, description)
            _PATTERNS: list[tuple[str, str, str]] = [
                # Hardcoded secrets
                (r'(?i)(password|passwd|pwd|secret|api_key|apikey|token|auth)\s*=\s*["\'][^"\']{4,}["\']',
                 "HIGH", "Захардкоженный секрет"),
                (r'(?i)(aws_access_key|aws_secret|private_key)\s*=\s*["\'][^"\']+["\']',
                 "CRITICAL", "Захардкоженный AWS/cloud ключ"),
                # SQL injection
                (r'(?i)(execute|cursor\.execute|query)\s*\(\s*f["\'].*\{',
                 "HIGH", "Потенциальная SQL-инъекция (f-строка в запросе)"),
                (r'(?i)(execute|cursor\.execute)\s*\(\s*["\'].*%s.*["\']\s*%\s*',
                 "MEDIUM", "SQL-запрос с %-форматированием"),
                # Dangerous builtins
                (r'\beval\s*\(', "HIGH", "Использование eval()"),
                (r'\bexec\s*\(', "HIGH", "Использование exec()"),
                # Subprocess with shell
                (r'subprocess\.(run|Popen|call|check_output).*shell\s*=\s*True',
                 "HIGH", "subprocess с shell=True (риск инъекции)"),
                # Unsafe deserialization
                (r'\bpickle\.loads?\s*\(', "HIGH", "Небезопасная десериализация (pickle)"),
                (r'\byaml\.load\s*\([^)]*\)', "MEDIUM", "yaml.load() без Loader (используйте safe_load)"),
                (r'\bmarshal\.loads?\s*\(', "HIGH", "Небезопасная десериализация (marshal)"),
                # Weak crypto
                (r'(?i)hashlib\.(md5|sha1)\s*\(', "LOW", "Слабый алгоритм хеширования"),
                (r'(?i)Crypto\.Cipher\.DES\b', "MEDIUM", "Слабый шифр DES"),
                # Debug markers
                (r'\bpdb\.set_trace\s*\(\)', "LOW", "Отладочный breakpoint (pdb)"),
                (r'\bbreakpoint\s*\(\)', "LOW", "Отладочный breakpoint()"),
                (r'(?i)TODO.*(security|auth|password|token|secret)',
                 "LOW", "TODO с упоминанием безопасности"),
                # Temp files
                (r'(?i)(tempfile\.mktemp|/tmp/["\'])', "LOW", "Небезопасное использование /tmp"),
                # HTTP without verification
                (r'verify\s*=\s*False', "MEDIUM", "SSL-верификация отключена"),
                (r'ssl\._create_unverified_context', "HIGH", "Небезопасный SSL-контекст"),
            ]

            p = _Path(text)
            if not p.exists():
                return f"Путь не найден: `{text}`"

            # Collect Python files
            py_files: list[_Path] = []
            if p.is_file():
                if p.suffix == ".py":
                    py_files = [p]
                else:
                    return f"Только .py файлы. Получен: `{p.suffix}`"
            else:
                _SKIP = {".git", "__pycache__", ".venv", "venv", "node_modules"}
                for f in p.rglob("*.py"):
                    if not any(s in f.parts for s in _SKIP):
                        py_files.append(f)
                py_files = py_files[:50]  # cap

            if not py_files:
                return f"Python-файлов не найдено в `{text}`."

            findings: list[tuple[str, int, str, str, str]] = []
            # (file, line, severity, description, snippet)

            for pyf in py_files:
                try:
                    lines = pyf.read_text(encoding="utf-8", errors="replace").splitlines()
                except Exception:
                    continue
                for lineno, line in enumerate(lines, 1):
                    for pattern, severity, desc in _PATTERNS:
                        if _re.search(pattern, line):
                            snippet = line.strip()[:80]
                            findings.append((str(pyf), lineno, severity, desc, snippet))

            if not findings:
                return (
                    f"✅ **Уязвимостей не обнаружено** в `{text}`\n\n"
                    f"*Проверено {len(py_files)} файлов, {len(_PATTERNS)} паттернов.*"
                )

            # Sort by severity
            _ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
            findings.sort(key=lambda x: (_ORDER.get(x[2], 9), x[0], x[1]))

            _ICONS = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵"}

            counts = {s: sum(1 for f in findings if f[2] == s) for s in ("CRITICAL", "HIGH", "MEDIUM", "LOW")}
            summary_parts = [f"{_ICONS[s]} {s}: {c}" for s, c in counts.items() if c > 0]

            lines_out = [
                f"**Security Scan: `{text}`**",
                f"Файлов: {len(py_files)} · Находок: {len(findings)}",
                "  ".join(summary_parts),
                "",
            ]

            shown = findings[:30]
            for fpath, lineno, severity, desc, snippet in shown:
                rel = _Path(fpath).name
                icon = _ICONS.get(severity, "⚪")
                lines_out.append(f"{icon} **[{severity}]** `{rel}:{lineno}` — {desc}")
                lines_out.append(f"   `{snippet}`")

            if len(findings) > 30:
                lines_out.append(f"\n*…ещё {len(findings) - 30} находок (показаны первые 30)*")

            lines_out.append(f"\n*Статический анализ, возможны ложные срабатывания.*")
            return "\n".join(lines_out)

        self.register(SlashCommand(
            "security-scan",
            "Сканирование уязвимостей: /security-scan <файл.py|директория>",
            security_scan_handler,
        ))

        # ── Task 230: /size-report ────────────────────────────────────────────

        async def size_report_handler(arg: str = "", **_) -> str:
            from pathlib import Path as _Path
            from collections import defaultdict as _dd

            text = arg.strip()
            root = _Path(text) if text else _Path(".")

            if not root.exists():
                return f"Путь не найден: `{text}`"

            _SKIP = {".git", "__pycache__", ".venv", "venv", "node_modules",
                     ".mypy_cache", ".pytest_cache", "dist", "build", ".eggs"}

            # Gather stats
            ext_stats: dict[str, dict] = _dd(lambda: {"files": 0, "lines": 0, "bytes": 0})
            dir_stats: dict[str, dict] = _dd(lambda: {"files": 0, "lines": 0, "bytes": 0})
            total_files = 0
            total_lines = 0
            total_bytes = 0
            largest: list[tuple[int, str]] = []  # (lines, path)

            def _walk(d: _Path) -> None:
                nonlocal total_files, total_lines, total_bytes
                try:
                    entries = list(d.iterdir())
                except PermissionError:
                    return
                for e in entries:
                    if e.name in _SKIP or e.name.startswith("."):
                        continue
                    if e.is_dir():
                        _walk(e)
                    elif e.is_file():
                        try:
                            raw = e.read_bytes()
                            size = len(raw)
                            total_files += 1
                            total_bytes += size
                            ext = e.suffix.lower() or "(без расш.)"
                            ext_stats[ext]["files"] += 1
                            ext_stats[ext]["bytes"] += size

                            # Line count for text files
                            if size < 500_000 and b"\x00" not in raw[:512]:
                                try:
                                    nlines = raw.decode("utf-8", errors="replace").count("\n")
                                    ext_stats[ext]["lines"] += nlines
                                    total_lines += nlines

                                    # Track for dir stats
                                    rel_dir = str(e.parent.relative_to(root))
                                    top_dir = rel_dir.split("/")[0].split("\\")[0] if rel_dir != "." else "."
                                    dir_stats[top_dir]["files"] += 1
                                    dir_stats[top_dir]["lines"] += nlines
                                    dir_stats[top_dir]["bytes"] += size

                                    largest.append((nlines, str(e.relative_to(root))))
                                except Exception:
                                    pass
                        except Exception:
                            pass

            _walk(root)

            if total_files == 0:
                return f"Файлов не найдено в `{root}`."

            def _fmt(n: int) -> str:
                if n < 1024:
                    return f"{n} Б"
                elif n < 1_048_576:
                    return f"{n/1024:.1f} КБ"
                else:
                    return f"{n/1_048_576:.1f} МБ"

            lines_out = [
                f"**Аналитика размера: `{root.resolve().name or '.'}`**",
                "",
                f"Файлов: **{total_files:,}** · "
                f"Строк: **{total_lines:,}** · "
                f"Размер: **{_fmt(total_bytes)}**",
                "",
            ]

            # By extension
            lines_out.append("**По типу файлов:**")
            sorted_ext = sorted(ext_stats.items(), key=lambda x: -x[1]["lines"])
            for ext, s in sorted_ext[:12]:
                bar = "█" * min(20, s["lines"] // max(1, total_lines // 20))
                lines_out.append(
                    f"  `{ext:<10}` {s['files']:>4} файл(а)  "
                    f"{s['lines']:>6} строк  {_fmt(s['bytes']):>10}  {bar}"
                )

            # By top-level directory
            if len(dir_stats) > 1:
                lines_out.append("")
                lines_out.append("**По директориям (верхний уровень):**")
                sorted_dirs = sorted(dir_stats.items(), key=lambda x: -x[1]["lines"])
                for dname, s in sorted_dirs[:10]:
                    pct = (s["lines"] / total_lines * 100) if total_lines else 0
                    lines_out.append(
                        f"  `{dname:<20}` {s['lines']:>6} строк ({pct:.0f}%)  {_fmt(s['bytes'])}"
                    )

            # Largest files
            largest.sort(reverse=True)
            if largest:
                lines_out.append("")
                lines_out.append("**Самые большие файлы (по строкам):**")
                for nlines, fpath in largest[:8]:
                    lines_out.append(f"  `{fpath}` — {nlines:,} строк")

            return "\n".join(lines_out)

        self.register(SlashCommand(
            "size-report",
            "Аналитика размера кодовой базы: /size-report [путь]",
            size_report_handler,
        ))

        # ── Task 231: /journal ────────────────────────────────────────────────

        async def journal_handler(arg: str = "", **_) -> str:
            import json as _json
            from pathlib import Path as _Path
            from datetime import datetime as _dt, date as _date

            journal_path = _Path(".lidco") / "journal.json"

            def _load() -> list:
                if journal_path.exists():
                    try:
                        return _json.loads(journal_path.read_text(encoding="utf-8"))
                    except Exception:
                        return []
                return []

            def _save(entries: list) -> None:
                journal_path.parent.mkdir(parents=True, exist_ok=True)
                journal_path.write_text(
                    _json.dumps(entries, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            text = arg.strip()

            # today — show today's entries
            if not text or text == "today":
                entries = _load()
                today_str = _date.today().isoformat()
                today_entries = [e for e in entries if e.get("date") == today_str]
                if not today_entries:
                    return (
                        f"**Журнал за {today_str}** — записей нет.\n\n"
                        "Добавьте: `/journal <текст>` или `/journal add <текст>`"
                    )
                lines = [f"**Журнал за {today_str}** ({len(today_entries)} записей)", ""]
                for e in today_entries:
                    time_str = e.get("time", "")
                    tag = f" `[{e['tag']}]`" if e.get("tag") else ""
                    lines.append(f"**{time_str}**{tag} {e['text']}")
                return "\n".join(lines)

            # list [N] — show last N days
            if text.startswith("list") or text.startswith("all"):
                parts = text.split()
                n_days = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 7
                entries = _load()
                if not entries:
                    return "Журнал пуст."
                # Group by date
                by_date: dict[str, list] = {}
                for e in entries:
                    d = e.get("date", "")
                    by_date.setdefault(d, []).append(e)
                # Last N days
                sorted_dates = sorted(by_date.keys(), reverse=True)[:n_days]
                lines = [f"**Журнал** (последние {n_days} дн., {len(entries)} записей)", ""]
                for d in sorted_dates:
                    lines.append(f"**{d}:**")
                    for e in by_date[d]:
                        time_str = e.get("time", "")
                        tag = f" `[{e['tag']}]`" if e.get("tag") else ""
                        lines.append(f"  {time_str}{tag} {e['text']}")
                return "\n".join(lines)

            # search <query>
            if text.startswith("search ") or text.startswith("find "):
                query = text.split(None, 1)[1].strip().lower()
                entries = _load()
                matches = [e for e in entries if query in e.get("text", "").lower()]
                if not matches:
                    return f"По запросу «{query}» ничего не найдено."
                lines = [f"**Найдено:** {len(matches)} записей", ""]
                for e in matches[-20:]:
                    lines.append(f"**{e.get('date')} {e.get('time','')}** {e['text']}")
                return "\n".join(lines)

            # stats
            if text == "stats":
                entries = _load()
                if not entries:
                    return "Журнал пуст."
                dates = {e.get("date") for e in entries}
                tags = {}
                for e in entries:
                    if e.get("tag"):
                        tags[e["tag"]] = tags.get(e["tag"], 0) + 1
                lines = [
                    f"**Статистика журнала**", "",
                    f"Записей: {len(entries)}",
                    f"Дней: {len(dates)}",
                    f"Среднее в день: {len(entries)/max(1,len(dates)):.1f}",
                ]
                if tags:
                    lines.append("\n**Теги:**")
                    for tag, cnt in sorted(tags.items(), key=lambda x: -x[1])[:10]:
                        lines.append(f"  `#{tag}`: {cnt}")
                return "\n".join(lines)

            # del N
            if text.startswith("del ") or text.startswith("delete "):
                idx_str = text.split(None, 1)[1].strip()
                if not idx_str.isdigit():
                    return "Укажите номер записи: `/journal del <N>`"
                entries = _load()
                idx = int(idx_str) - 1
                if idx < 0 or idx >= len(entries):
                    return f"Запись #{idx_str} не найдена."
                removed = entries.pop(idx)
                _save(entries)
                return f"Удалена запись: *{removed['text'][:60]}*"

            # clear
            if text == "clear":
                entries = _load()
                _save([])
                return f"Журнал очищен ({len(entries)} записей удалено)."

            # add <text> — strip "add " prefix if present
            if text.startswith("add "):
                text = text[4:].strip()

            # Parse optional #tag
            tag = ""
            if text.startswith("#"):
                parts = text.split(None, 1)
                tag = parts[0][1:]
                text = parts[1].strip() if len(parts) > 1 else ""
                if not text:
                    return "Укажите текст записи: `/journal #tag текст`"

            now = _dt.now()
            entries = _load()
            entries.append({
                "text": text,
                "tag": tag,
                "date": now.date().isoformat(),
                "time": now.strftime("%H:%M"),
            })
            _save(entries)
            tag_str = f" `[{tag}]`" if tag else ""
            return f"✓ Запись #{len(entries)} добавлена{tag_str}: *{text[:80]}*"

        self.register(SlashCommand(
            "journal",
            "Dev-журнал: /journal [add|today|list|search|stats|del|clear]",
            journal_handler,
        ))

        # ── Task 232: /table ──────────────────────────────────────────────────

        async def table_handler(arg: str = "", **_) -> str:
            import csv as _csv
            import io as _io
            from pathlib import Path as _Path

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/table <csv_файл или данные> [--sep ,] [--no-header]`\n\n"
                    "Рендеринг CSV как таблицы.\n\n"
                    "  `/table data.csv` — из файла\n"
                    "  `/table \"name,age\\nAlice,30\\nBob,25\"` — из текста\n"
                    "  `/table data.csv --sep ;` — с разделителем `;`"
                )

            sep = ","
            has_header = True
            if "--sep" in text:
                parts = text.split("--sep", 1)
                text = parts[0].strip()
                sep_tok = parts[1].strip().split()[0]
                sep = sep_tok if sep_tok else ","
            if "--no-header" in text:
                has_header = False
                text = text.replace("--no-header", "").strip()

            # Try as file first
            source_label = "inline"
            raw_csv = text
            p = _Path(text)
            if p.exists() and p.is_file():
                try:
                    raw_csv = p.read_text(encoding="utf-8", errors="replace")
                    source_label = p.name
                except Exception as exc:
                    return f"Ошибка чтения файла: {exc}"
            else:
                # Allow \n escape in inline data
                raw_csv = raw_csv.replace("\\n", "\n")

            try:
                reader = _csv.reader(_io.StringIO(raw_csv), delimiter=sep)
                rows = list(reader)
            except Exception as exc:
                return f"Ошибка парсинга CSV: {exc}"

            if not rows:
                return "CSV пуст."

            # Cap rows
            max_rows = 50
            truncated = len(rows) > max_rows + (1 if has_header else 0)

            if has_header:
                headers = rows[0]
                data_rows = rows[1:max_rows + 1]
            else:
                headers = [f"Col{i+1}" for i in range(len(rows[0]))]
                data_rows = rows[:max_rows]

            if not headers:
                return "CSV не содержит столбцов."

            # Calculate column widths
            col_widths = [len(h) for h in headers]
            for row in data_rows:
                for i, cell in enumerate(row):
                    if i < len(col_widths):
                        col_widths[i] = max(col_widths[i], min(len(cell), 30))

            def _fmt_row(cells: list[str]) -> str:
                parts = []
                for i, w in enumerate(col_widths):
                    cell = cells[i] if i < len(cells) else ""
                    cell = cell[:30]  # truncate long cells
                    parts.append(cell.ljust(w))
                return "│ " + " │ ".join(parts) + " │"

            sep_line = "├─" + "─┼─".join("─" * w for w in col_widths) + "─┤"
            top_line = "┌─" + "─┬─".join("─" * w for w in col_widths) + "─┐"
            bot_line = "└─" + "─┴─".join("─" * w for w in col_widths) + "─┘"

            lines = [
                f"**Таблица: `{source_label}`** "
                f"({len(data_rows)} строк × {len(headers)} столбцов)",
                "",
                "```",
                top_line,
                _fmt_row(headers),
                sep_line,
            ]
            for row in data_rows:
                lines.append(_fmt_row(row))
            lines.append(bot_line)
            lines.append("```")

            if truncated:
                total = len(rows) - (1 if has_header else 0)
                lines.append(f"\n*Показано {len(data_rows)} из {total} строк.*")

            return "\n".join(lines)

        self.register(SlashCommand(
            "table",
            "Рендер CSV как таблицы: /table <файл.csv|данные> [--sep ,] [--no-header]",
            table_handler,
        ))

        # ── Task 233: /api ────────────────────────────────────────────────────

        async def api_handler(arg: str = "", **_) -> str:
            import asyncio as _asyncio
            import json as _json

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/api <url> [метод] [тело] [--header K:V]`\n\n"
                    "HTTP-клиент прямо в REPL.\n\n"
                    "  `/api https://httpbin.org/get` — GET запрос\n"
                    "  `/api https://httpbin.org/post POST '{\"key\":\"val\"}'`\n"
                    "  `/api https://api.example.com DELETE --header Authorization:Bearer_token`"
                )

            # Parse method
            _METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
            parts = text.split(None, 2)
            url = parts[0]
            method = "GET"
            body = ""
            headers: dict[str, str] = {"User-Agent": "LIDCO/1.0"}

            rest = " ".join(parts[1:]) if len(parts) > 1 else ""

            # Extract --header flags
            import re as _re
            header_matches = _re.findall(r'--header\s+(\S+):(\S+)', rest)
            for k, v in header_matches:
                headers[k] = v.replace("_", " ")
            rest = _re.sub(r'--header\s+\S+:\S+', "", rest).strip()

            rest_parts = rest.split(None, 1)
            if rest_parts and rest_parts[0].upper() in _METHODS:
                method = rest_parts[0].upper()
                body = rest_parts[1].strip() if len(rest_parts) > 1 else ""
            elif rest_parts:
                body = rest.strip()

            # Validate URL
            if not url.startswith(("http://", "https://")):
                return f"URL должен начинаться с http:// или https://. Получено: `{url}`"

            # Execute via urllib (no external deps)
            import urllib.request as _urllib
            import urllib.error as _urlerr

            try:
                req_body = body.encode("utf-8") if body else None
                if req_body and "Content-Type" not in headers:
                    try:
                        _json.loads(body)
                        headers["Content-Type"] = "application/json"
                    except Exception:
                        headers["Content-Type"] = "text/plain"

                req = _urllib.Request(url, data=req_body, headers=headers, method=method)

                import asyncio as _aio
                loop = _aio.get_event_loop()

                def _do_request():
                    with _urllib.urlopen(req, timeout=10) as resp:
                        status = resp.status
                        resp_headers = dict(resp.headers)
                        resp_body = resp.read().decode("utf-8", errors="replace")
                        return status, resp_headers, resp_body

                status, resp_headers, resp_body = await loop.run_in_executor(None, _do_request)

            except _urlerr.HTTPError as exc:
                status = exc.code
                resp_headers = {}
                try:
                    resp_body = exc.read().decode("utf-8", errors="replace")
                except Exception:
                    resp_body = str(exc)
            except Exception as exc:
                return f"Ошибка запроса: {exc}"

            # Format response
            status_icon = "✅" if 200 <= status < 300 else ("⚠️" if 200 <= status < 400 else "❌")
            lines = [
                f"**{method} {url}**",
                "",
                f"{status_icon} **Статус:** `{status}`",
            ]

            # Content-type
            ct = resp_headers.get("Content-Type", resp_headers.get("content-type", ""))
            if ct:
                lines.append(f"**Content-Type:** `{ct}`")

            lines.append("")

            # Body
            body_display = resp_body[:3000]
            if resp_body.strip().startswith("{") or resp_body.strip().startswith("["):
                try:
                    parsed = _json.loads(resp_body)
                    body_display = _json.dumps(parsed, indent=2, ensure_ascii=False)[:3000]
                    lang = "json"
                except Exception:
                    lang = ""
            else:
                lang = ""

            lines.append(f"```{lang}")
            lines.append(body_display)
            lines.append("```")

            if len(resp_body) > 3000:
                lines.append(f"\n*…обрезано ({len(resp_body):,} символов всего)*")

            return "\n".join(lines)

        self.register(SlashCommand(
            "api",
            "HTTP-клиент: /api <url> [GET|POST|...] [тело] [--header K:V]",
            api_handler,
        ))

        # ── Task 234: /lint-fix ───────────────────────────────────────────────

        async def lint_fix_handler(arg: str = "", **_) -> str:
            import asyncio as _asyncio
            from pathlib import Path as _Path

            text = arg.strip()
            if not text:
                return (
                    "**Использование:** `/lint-fix <файл.py или директория> [--check]`\n\n"
                    "Автоматическое исправление lint-ошибок через ruff.\n\n"
                    "  `/lint-fix src/utils.py` — исправить файл\n"
                    "  `/lint-fix src/ --check` — показать что будет исправлено\n"
                    "  `/lint-fix .` — исправить всё в текущей директории"
                )

            check_only = "--check" in text
            if check_only:
                text = text.replace("--check", "").strip()

            p = _Path(text)
            if not p.exists():
                return f"Путь не найден: `{text}`"

            async def _ruff(*args, timeout=30) -> tuple[int, str]:
                try:
                    proc = await _asyncio.create_subprocess_exec(
                        "ruff", *args,
                        stdout=_asyncio.subprocess.PIPE,
                        stderr=_asyncio.subprocess.STDOUT,
                    )
                    out, _ = await _asyncio.wait_for(proc.communicate(), timeout=timeout)
                    return proc.returncode or 0, out.decode("utf-8", errors="replace").strip()
                except FileNotFoundError:
                    return 1, "ruff не найден. Установите: `pip install ruff`"
                except _asyncio.TimeoutError:
                    return 1, "Timeout (30s)"
                except Exception as exc:
                    return 1, str(exc)

            # First: check what would be fixed
            rc_check, check_out = await _ruff("check", str(p), "--no-fix")

            if check_only:
                if rc_check == 0:
                    return f"✅ `{p}` — lint-ошибок нет."
                lines = [
                    f"**ruff check** `{p}` (режим --check)",
                    "",
                    "```",
                ]
                for line in check_out.splitlines()[:40]:
                    lines.append(line)
                lines.append("```")
                count = sum(1 for l in check_out.splitlines() if ".py:" in l)
                if count:
                    lines.append(f"\n*{count} проблем будет исправлено командой `/lint-fix {text}`*")
                return "\n".join(lines)

            if rc_check == 0:
                return f"✅ `{p}` — lint-ошибок нет, исправление не требуется."

            # Count before
            before_count = sum(1 for l in check_out.splitlines() if ".py:" in l)

            # Apply fixes
            rc_fix, fix_out = await _ruff("check", str(p), "--fix")

            # Count after
            rc_after, after_out = await _ruff("check", str(p), "--no-fix")
            after_count = sum(1 for l in after_out.splitlines() if ".py:" in l) if rc_after != 0 else 0

            fixed = before_count - after_count

            lines = [f"**ruff --fix** `{p}`", ""]

            if fixed > 0:
                lines.append(f"✅ Исправлено: **{fixed}** проблем")
            if after_count > 0:
                lines.append(f"⚠️  Осталось: **{after_count}** (требуют ручного исправления)")

            if fix_out:
                lines.append("")
                lines.append("```")
                for line in fix_out.splitlines()[:20]:
                    lines.append(line)
                lines.append("```")

            if after_count > 0 and after_out:
                lines.append("\n**Оставшиеся проблемы:**")
                lines.append("```")
                for line in after_out.splitlines()[:20]:
                    lines.append(line)
                lines.append("```")

            return "\n".join(lines)

        self.register(SlashCommand(
            "lint-fix",
            "Автоисправление lint: /lint-fix <файл|директория> [--check]",
            lint_fix_handler,
        ))

