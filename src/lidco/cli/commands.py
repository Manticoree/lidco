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

        async def agents_handler(arg: str = "", **_: Any) -> str:
            """List available agents and manage background tasks.

            /agents              — list all registered agents
            /agents bg           — list background tasks
            /agents bg stop <id> — cancel a background task
            /agents inspect <name> — show agent config details
            """
            if not registry._session:
                return "Session not initialized."

            raw = (arg or "").strip()

            # /agents bg [stop <id>]
            if raw == "bg" or raw.startswith("bg "):
                bg_mgr = getattr(registry._session, "background_tasks", None)
                if bg_mgr is None:
                    return "Background task manager not available."

                rest = raw[3:].strip() if raw.startswith("bg ") else ""

                if rest.startswith("stop "):
                    task_id = rest[5:].strip()
                    if bg_mgr.cancel(task_id):
                        return f"Task `{task_id}` cancelled."
                    return f"Task `{task_id}` not found or already done."

                tasks = bg_mgr.list_all()
                if not tasks:
                    return "No background tasks."
                lines = ["**Background Tasks**\n"]
                for bt in tasks:
                    icon = {"running": "⟳", "done": "✓", "failed": "✗", "cancelled": "⊘"}.get(bt.status, "?")
                    elapsed = ""
                    if bt.finished_at:
                        secs = (bt.finished_at - bt.started_at).total_seconds()
                        elapsed = f" ({secs:.1f}s)"
                    lines.append(
                        f"- `{bt.task_id}` {icon} **{bt.status}**{elapsed} — "
                        f"[{bt.agent_name or 'auto'}] {bt.task[:60]}"
                    )
                lines.append("\nUse `/agents bg stop <id>` to cancel a running task.")
                return "\n".join(lines)

            # /agents inspect <name>
            if raw.startswith("inspect "):
                agent_name = raw[8:].strip()
                agent = registry._session.agent_registry.get(agent_name)
                if agent is None:
                    return f"Agent `{agent_name}` not found."
                cfg = agent._config
                lines = [f"**Agent: {cfg.name}**\n"]
                lines.append(f"Description: {cfg.description or '(none)'}")
                lines.append(f"Model: {cfg.model or 'default'}")
                lines.append(f"Temperature: {cfg.temperature}")
                lines.append(f"Max iterations: {cfg.max_iterations}")
                if cfg.tools:
                    lines.append(f"Tools: {', '.join(cfg.tools)}")
                if cfg.disallowed_tools:
                    lines.append(f"Disallowed: {', '.join(cfg.disallowed_tools)}")
                if cfg.permission_mode:
                    lines.append(f"Permission mode: {cfg.permission_mode}")
                if cfg.isolation != "none":
                    lines.append(f"Isolation: {cfg.isolation}")
                if cfg.memory != "project":
                    lines.append(f"Memory: {cfg.memory}")
                if cfg.routing_keywords:
                    lines.append(f"Keywords: {', '.join(cfg.routing_keywords)}")
                return "\n".join(lines)

            # default: list all agents
            agents = registry._session.agent_registry.list_agents()
            lines = ["**Available agents:**\n"]
            for agent in agents:
                cfg = agent._config
                tags = []
                if cfg.permission_mode:
                    tags.append(cfg.permission_mode)
                if cfg.isolation != "none":
                    tags.append(f"isolation:{cfg.isolation}")
                tag_str = f" [{', '.join(tags)}]" if tags else ""
                lines.append(f"- **{agent.name}**{tag_str}: {agent.description}")
            lines.append("")
            lines.append("Use `@agent_name message` to target a specific agent.")
            lines.append("Use `/agents inspect <name>` for details.")
            bg_count = getattr(getattr(registry._session, "background_tasks", None), "running_count", lambda: 0)()
            if bg_count:
                lines.append(f"\n{bg_count} background task(s) running. Use `/agents bg` to view.")
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
            # Q55/373: also support --html format via SessionExporter
            parts = arg.split() if arg else []
            use_md = "--md" in parts or "--format" in parts and "md" in parts
            use_html = "--html" in parts or (
                "--format" in parts
                and len(parts) > parts.index("--format") + 1
                and parts[parts.index("--format") + 1] == "html"
            )
            flag_set = {"--md", "--html", "--format"}
            path_parts = [
                p for p in parts
                if p not in flag_set and (not p.startswith("--format") if p != "--format" else False)
            ]
            # remove format value after --format
            if "--format" in parts:
                fi = parts.index("--format")
                if fi + 1 < len(parts):
                    path_parts = [p for p in path_parts if p != parts[fi + 1]]
            explicit_path = path_parts[0] if path_parts else ""

            if use_html:
                from lidco.cli.session_exporter import SessionExporter
                export_dir = Path(".lidco") / "exports"
                exporter = SessionExporter(
                    history=list(history),
                    session_id=getattr(registry._session_store, "_current_id", "session") if hasattr(registry, "_session_store") else "session",
                    metadata={"model": model, "tokens": tokens, "cost_usd": cost_usd},
                )
                out_path = exporter.export(format="html", output_dir=export_dir)
                return f"Session exported to `{out_path}` ({len(history)} messages)"

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
            from pathlib import Path

            from lidco.cli.init_generator import InitGenerator
            from lidco.core.rules import RulesManager

            project_dir = (
                registry._session.project_dir
                if registry._session
                else Path.cwd()
            )
            rules_mgr = RulesManager(project_dir)

            if rules_mgr.has_rules_file() and "--force" not in (arg or ""):
                return (
                    f"**LIDCO.md** already exists at `{rules_mgr.rules_file}`.\n\n"
                    "Use `/init --force` to regenerate it, or `/rules` to manage rules."
                )

            gen = InitGenerator(project_dir)
            profile = gen.analyze()
            content = gen.generate(profile)

            if rules_mgr.has_rules_file() and "--force" in (arg or ""):
                rules_mgr.rules_file.write_text(content, encoding="utf-8")
                return f"Regenerated **LIDCO.md** at `{rules_mgr.rules_file}` based on project analysis."

            try:
                rules_mgr.rules_file.write_text(content, encoding="utf-8")
                rules_mgr.rules_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                return f"Failed to create LIDCO.md: {e}"

            sources = (
                f"\n\nDetected: **{profile.language}**"
                + (f" / {profile.framework}" if profile.framework else "")
                + (f" · tests: `{profile.test_runner}`" if profile.test_runner else "")
            )
            return (
                f"Created **LIDCO.md** at `{rules_mgr.rules_file}`{sources}\n\n"
                "Edit it freely — agents read it on every session start.\n"
                "Use `/rules` to manage rules, `/permissions` to manage tool access."
            )

        async def permissions_handler(arg: str = "", **_: Any) -> str:
            """View and manage permission rules."""
            from rich.table import Table

            if not registry._session:
                return "Session not initialized."

            engine = registry._session.permission_engine
            summary = engine.get_summary()
            arg = (arg or "").strip()

            # Subcommands
            if arg.startswith("mode "):
                new_mode = arg[5:].strip()
                valid_modes = {"default", "accept_edits", "plan", "dont_ask", "bypass"}
                if new_mode not in valid_modes:
                    return f"Invalid mode. Valid: {', '.join(sorted(valid_modes))}"
                engine.set_mode(new_mode)
                return f"Permission mode set to **{new_mode}**"

            if arg.startswith("add "):
                parts_arg = arg[4:].strip().split(None, 1)
                if len(parts_arg) < 2:
                    return "Usage: `/permissions add allow|ask|deny Rule(pattern)`"
                level, rule_spec = parts_arg[0], parts_arg[1]
                if level == "allow":
                    engine.add_persistent_allow(rule_spec)
                elif level == "deny":
                    engine.add_persistent_deny(rule_spec)
                elif level == "ask":
                    engine._ask_rules.append(
                        __import__("lidco.core.permission_engine", fromlist=["RuleParser"]).RuleParser.parse(rule_spec)
                    )
                else:
                    return "Level must be: allow | ask | deny"
                return f"Added **{level}** rule: `{rule_spec}`"

            if arg.startswith("remove "):
                return "Use `/permissions remove allow N` or `deny N` (0-indexed)."

            if arg == "clear":
                engine._session_allowed.clear()
                engine._session_denied.clear()
                return "Session permission decisions cleared."

            if arg == "save":
                engine._save()
                return f"Rules saved to `.lidco/permissions.json`"

            # Default: show summary
            mode_color = {
                "default": "white", "accept_edits": "green", "plan": "yellow",
                "dont_ask": "red", "bypass": "magenta",
            }.get(summary["mode"], "white")

            lines = [f"**Permission Mode:** [{mode_color}]{summary['mode']}[/{mode_color}]\n"]

            def _section(title: str, rules: list[str], color: str) -> None:
                if rules:
                    lines.append(f"**{title}** ({len(rules)})")
                    for r in rules:
                        lines.append(f"  [{color}]✓[/{color}] `{r}`")
                    lines.append("")

            _section("Command allowlist", summary["command_allowlist"], "green")
            _section("Config allow_rules", summary["allow_rules"], "green")
            _section("Config ask_rules", summary["ask_rules"], "yellow")
            _section("Config deny_rules", summary["deny_rules"], "red")
            _section("Persistent allow", summary["persistent_allow"], "green")
            _section("Persistent deny", summary["persistent_deny"], "red")
            _section("Session allowed", summary["session_allowed"], "cyan")
            _section("Session denied", summary["session_denied"], "dim")

            lines.append(
                "\n**Subcommands:** `mode <mode>` · `add allow|ask|deny Rule(pat)` · `clear` · `save`"
            )
            return "\n".join(lines)

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
        self.register(SlashCommand("init", "Generate LIDCO.md from project analysis [--force]", init_handler))
        self.register(SlashCommand("permissions", "View and manage tool permission rules", permissions_handler))
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

        # ── Task 235: /refactor ───────────────────────────────────────────────

        async def refactor_handler(arg: str = "", **_) -> str:
            if not arg.strip():
                return (
                    "**Использование:** `/refactor <файл> [инструкция]`\n\n"
                    "Примеры:\n"
                    "- `/refactor utils.py` — общий рефакторинг\n"
                    "- `/refactor auth.py извлеки функции` — по инструкции\n"
                    "- `/refactor module.py --dry` — только показать предложения"
                )
            if self._session is None:
                return "❌ Сессия не инициализирована. Начните сессию перед использованием `/refactor`."

            parts = arg.strip().split(None, 1)
            file_part = parts[0]
            instruction = parts[1] if len(parts) > 1 else ""

            # Handle --dry flag
            dry_run = False
            if "--dry" in instruction:
                dry_run = True
                instruction = instruction.replace("--dry", "").strip()
            elif file_part == "--dry":
                return "**Использование:** `/refactor <файл> [--dry]`"

            p = Path(file_part)
            if not p.exists():
                return f"❌ Файл не найден: `{file_part}`"
            if not p.is_file():
                return f"❌ `{file_part}` — не файл."
            if p.suffix != ".py":
                return f"❌ Поддерживаются только `.py` файлы (получен `{p.suffix}`)."

            try:
                source = p.read_text(encoding="utf-8")
            except Exception as e:
                return f"❌ Ошибка чтения файла: {e}"

            loc = len(source.splitlines())
            if loc > 1000:
                return (
                    f"⚠️ Файл слишком большой ({loc} строк). "
                    "Используйте `/refactor <файл> <функция>` для рефакторинга конкретной части."
                )

            model = self._session.config.llm.default_model
            hint = f"\n\nИнструкция: {instruction}" if instruction else ""
            prompt = (
                f"Проанализируй следующий Python-файл и предложи рефакторинг.{hint}\n"
                "Верни улучшенный код ЦЕЛИКОМ, обёрнутый в ```python ... ```.\n"
                "После кода добавь секцию ## Изменения с кратким списком того, что было изменено.\n\n"
                f"Файл: {p.name}\n\n```python\n{source}\n```"
            )

            try:
                resp = await self._session.llm.complete(
                    [{"role": "user", "content": prompt}],
                    model=model,
                    max_tokens=4096,
                )
                content = resp.content if hasattr(resp, "content") else str(resp)
            except Exception as e:
                return f"❌ Ошибка LLM: {e}"

            if dry_run:
                return f"**Предложения по рефакторингу** `{p.name}` (режим --dry, файл не изменён)\n\n{content}"

            # Extract code block
            import re as _re
            code_match = _re.search(r"```python\n(.*?)```", content, _re.DOTALL)
            if not code_match:
                return f"**Предложения по рефакторингу** `{p.name}`\n\n{content}"

            new_source = code_match.group(1)
            if new_source.strip() == source.strip():
                return f"✅ `{p.name}` — рефакторинг не требуется, код уже оптимален.\n\n{content}"

            try:
                p.write_text(new_source, encoding="utf-8")
            except Exception as e:
                return f"❌ Ошибка записи файла: {e}"

            # Extract changes section
            changes_match = _re.search(r"## Изменения(.*?)(?:##|$)", content, _re.DOTALL)
            changes = changes_match.group(1).strip() if changes_match else ""

            lines = [f"✅ **Рефакторинг** `{p.name}` — файл обновлён"]
            if changes:
                lines.append(f"\n**Изменения:**\n{changes}")
            lines.append(f"\n*Применено к {p}*")
            return "\n".join(lines)

        self.register(SlashCommand(
            "refactor",
            "AI-рефакторинг: /refactor <файл> [инструкция|--dry]",
            refactor_handler,
        ))

        # ── Task 236: /chart ──────────────────────────────────────────────────

        async def chart_handler(arg: str = "", **_) -> str:
            if not arg.strip():
                return (
                    "**Использование:** `/chart <данные> [--type bar|line|pie] [--title Заголовок]`\n\n"
                    "Форматы данных:\n"
                    "- `10,20,30,40` — список чисел\n"
                    "- `Jan:10,Feb:20,Mar:30` — метки:значения\n"
                    "- `10 20 30 40` — пробелами\n\n"
                    "Примеры:\n"
                    "- `/chart 10,25,15,40 --type bar`\n"
                    "- `/chart Jan:10,Feb:20,Mar:5 --type line`\n"
                    "- `/chart Python:40,JS:30,Rust:20,Other:10 --type pie`"
                )

            import re as _re

            raw = arg.strip()

            # Extract flags
            chart_type = "bar"
            m_type = _re.search(r"--type\s+(bar|line|pie)", raw)
            if m_type:
                chart_type = m_type.group(1)
                raw = raw[:m_type.start()].strip() + raw[m_type.end():].strip()

            title = ""
            m_title = _re.search(r"--title\s+(.+?)(?:\s+--|$)", raw)
            if m_title:
                title = m_title.group(1).strip()
                raw = raw[:m_title.start()].strip() + raw[m_title.end():].strip()

            raw = raw.strip()

            # Parse data: label:value,label:value OR value,value OR value value
            labels: list[str] = []
            values: list[float] = []

            try:
                if ":" in raw:
                    for item in raw.replace(";", ",").split(","):
                        item = item.strip()
                        if not item:
                            continue
                        if ":" in item:
                            lbl, val = item.rsplit(":", 1)
                            labels.append(lbl.strip())
                            values.append(float(val.strip()))
                        else:
                            labels.append(f"#{len(values)+1}")
                            values.append(float(item))
                else:
                    sep = "," if "," in raw else None
                    parts_v = raw.split(sep) if sep else raw.split()
                    for i, v in enumerate(parts_v):
                        v = v.strip()
                        if v:
                            labels.append(f"#{i+1}")
                            values.append(float(v))
            except ValueError as e:
                return f"❌ Ошибка парсинга данных: {e}\n\nОжидается формат: `10,20,30` или `A:10,B:20`"

            if not values:
                return "❌ Нет данных для построения графика."

            if len(values) > 30:
                return f"❌ Слишком много точек ({len(values)}). Максимум 30."

            max_val = max(values)
            min_val = min(values)
            total = sum(values)

            header = f"**{title}**\n" if title else ""
            type_label = {"bar": "Столбчатая", "line": "Линейная", "pie": "Круговая"}[chart_type]
            header += f"*{type_label} диаграмма — {len(values)} точек*\n\n"

            if chart_type in ("bar", "line"):
                # ASCII bar / line chart
                W = 40
                rows = []

                if chart_type == "bar":
                    max_lbl = max(len(l) for l in labels)
                    for lbl, val in zip(labels, values):
                        bar_len = int(round((val / max_val) * W)) if max_val > 0 else 0
                        bar = "█" * bar_len
                        rows.append(f"{lbl:>{max_lbl}} │{bar:<{W}} {val:g}")
                else:
                    # Line chart: plot on a 2D grid
                    H = min(10, len(values))
                    grid = [[" "] * len(values) for _ in range(H)]
                    rng = max_val - min_val if max_val != min_val else 1
                    for i, val in enumerate(values):
                        row = int(round((H - 1) * (1 - (val - min_val) / rng)))
                        row = max(0, min(H - 1, row))
                        grid[row][i] = "●"
                    for row_idx, row in enumerate(grid):
                        y_val = max_val - (max_val - min_val) * row_idx / max(H - 1, 1)
                        rows.append(f"{y_val:>7.1f} │{''.join(row)}")
                    rows.append(" " * 8 + "└" + "─" * len(values))
                    max_lbl = max(len(l) for l in labels)
                    rows.append(" " * 9 + "  ".join(f"{l:>{max_lbl}}" for l in labels)[:80])

                output = header + "```\n" + "\n".join(rows) + "\n```"

            else:
                # Pie chart: ASCII representation
                rows = []
                chars = "▓░▒▪▫◆◇●○■□"
                for i, (lbl, val) in enumerate(zip(labels, values)):
                    pct = (val / total * 100) if total > 0 else 0
                    bar_len = int(round(pct / 100 * 30))
                    ch = chars[i % len(chars)]
                    rows.append(f"{ch * bar_len:<30} {lbl}: {val:g} ({pct:.1f}%)")
                output = header + "```\n" + "\n".join(rows) + "\n```"

            # Stats footer
            stats = (
                f"\n*Мин: {min_val:g}  Макс: {max_val:g}  "
                f"Сумма: {total:g}  Среднее: {total/len(values):.2f}*"
            )
            return output + stats

        self.register(SlashCommand(
            "chart",
            "ASCII-диаграмма: /chart <данные> [--type bar|line|pie] [--title ...]",
            chart_handler,
        ))

        # ── Task 237: /perf ───────────────────────────────────────────────────

        async def perf_handler(arg: str = "", **_) -> str:
            if not arg.strip():
                return (
                    "**Использование:** `/perf <файл.py> [функция] [--top N] [--calls]`\n\n"
                    "Примеры:\n"
                    "- `/perf script.py` — профилировать весь файл\n"
                    "- `/perf script.py main` — профилировать функцию main\n"
                    "- `/perf script.py --top 20` — показать top-20 функций\n"
                    "- `/perf script.py --calls` — включить дерево вызовов"
                )

            import re as _re
            import sys

            raw = arg.strip()

            # Extract flags
            top_n = 10
            m_top = _re.search(r"--top\s+(\d+)", raw)
            if m_top:
                top_n = int(m_top.group(1))
                raw = raw[:m_top.start()].strip() + raw[m_top.end():].strip()

            show_calls = "--calls" in raw
            if show_calls:
                raw = raw.replace("--calls", "").strip()

            parts = raw.split(None, 1)
            file_part = parts[0]
            func_name = parts[1].strip() if len(parts) > 1 else ""

            p = Path(file_part)
            if not p.exists():
                return f"❌ Файл не найден: `{file_part}`"
            if not p.is_file():
                return f"❌ `{file_part}` — не файл."
            if p.suffix != ".py":
                return f"❌ Поддерживаются только `.py` файлы."

            # Build a profiling script that runs the target and dumps stats
            import asyncio
            import tempfile, json as _json

            prof_script = f"""\
import cProfile
import pstats
import io
import sys
import json

sys.path.insert(0, r"{p.parent}")

pr = cProfile.Profile()
pr.enable()

try:
    import runpy
    runpy.run_path(r"{p}", run_name="__main__")
except SystemExit:
    pass
except Exception as exc:
    pass
finally:
    pr.disable()

s = io.StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
ps.print_stats({top_n})
stats_text = s.getvalue()
print(stats_text)
"""
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
                tf.write(prof_script)
                tf_name = tf.name

            try:
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, tf_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
                except asyncio.TimeoutError:
                    proc.kill()
                    return f"❌ Профилирование прервано: превышен лимит 30 секунд."
            finally:
                import os as _os
                try:
                    _os.unlink(tf_name)
                except Exception:
                    pass

            out = stdout.decode("utf-8", errors="replace")
            err = stderr.decode("utf-8", errors="replace")

            if not out.strip() and err.strip():
                err_lines = err.splitlines()[:10]
                return f"❌ Ошибка выполнения:\n```\n" + "\n".join(err_lines) + "\n```"

            # Parse pstats output into a table
            lines_out = out.splitlines()
            # Find the header line
            table_start = None
            for i, ln in enumerate(lines_out):
                if "ncalls" in ln and "tottime" in ln:
                    table_start = i
                    break

            result_lines = [
                f"**Профиль** `{p.name}`  (top {top_n} по cumtime)",
                "",
            ]

            if table_start is not None:
                # Header
                result_lines.append("```")
                header_line = lines_out[table_start]
                result_lines.append(header_line)
                result_lines.append("-" * min(len(header_line), 80))

                data_rows = []
                for ln in lines_out[table_start + 1:]:
                    if not ln.strip():
                        continue
                    data_rows.append(ln)
                    if len(data_rows) >= top_n:
                        break

                result_lines.extend(data_rows)
                result_lines.append("```")
            else:
                # Fallback: show raw output
                result_lines.append("```")
                for ln in lines_out[:min(len(lines_out), top_n + 10)]:
                    result_lines.append(ln)
                result_lines.append("```")

            # Summary: total time from "function calls in X seconds"
            for ln in lines_out:
                if "function calls" in ln and "seconds" in ln:
                    result_lines.append(f"\n*{ln.strip()}*")
                    break

            # Call tree hint
            if show_calls:
                result_lines.append("\n**Совет:** Для дерева вызовов используйте `snakeviz` или `py-spy`.")

            # Hotspot hint
            if data_rows if table_start is not None else False:
                first_row = data_rows[0] if data_rows else ""
                result_lines.append(
                    f"\n💡 Самая медленная функция: `{first_row.rsplit(None, 1)[-1] if first_row else '?'}`"
                )

            return "\n".join(result_lines)

        self.register(SlashCommand(
            "perf",
            "Профилирование Python: /perf <файл.py> [--top N] [--calls]",
            perf_handler,
        ))

        # ── Task 238: /env ────────────────────────────────────────────────────

        async def env_handler(arg: str = "", **_) -> str:
            import os as _os
            import re as _re

            raw = arg.strip()

            # /env --export
            if raw == "--export":
                lines = ["**Export:**", "```bash"]
                for k, v in sorted(_os.environ.items()):
                    lines.append(f"export {k}={v!r}")
                lines.append("```")
                return "\n".join(lines)

            # /env unset VAR
            if raw == "unset" or raw.startswith("unset "):
                key = raw[6:].strip() if raw.startswith("unset ") else ""
                if not key:
                    return "❌ Укажите имя переменной: `/env unset VAR`"
                if key in _os.environ:
                    del _os.environ[key]
                    return f"✓ Переменная `{key}` удалена из окружения."
                return f"⚠️ `{key}` не установлена."

            # /env --filter PATTERN
            m_filter = _re.match(r"--filter\s+(.+)", raw)
            if m_filter:
                pat = m_filter.group(1).strip().lower()
                matches = {k: v for k, v in _os.environ.items() if pat in k.lower() or pat in v.lower()}
                if not matches:
                    return f"*Нет переменных, содержащих `{pat}`.*"
                lines = [f"**Переменные окружения** (фильтр: `{pat}`):\n"]
                for k in sorted(matches):
                    v = matches[k]
                    display = v if len(v) <= 60 else v[:60] + "…"
                    lines.append(f"- `{k}` = `{display}`")
                return "\n".join(lines)

            # /env VAR=value — set
            if "=" in raw and not raw.startswith("-"):
                key, _, val = raw.partition("=")
                key = key.strip()
                val = val.strip()
                if not key or not _re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                    return f"❌ Некорректное имя переменной: `{key}`"
                _os.environ[key] = val
                return f"✓ `{key}` = `{val}`"

            # /env VAR — show one
            if raw and not raw.startswith("-"):
                val = _os.environ.get(raw)
                if val is None:
                    return f"⚠️ Переменная `{raw}` не установлена."
                return f"**{raw}** = `{val}`"

            # /env — list all (grouped by prefix)
            env = _os.environ
            total = len(env)
            MAX = 50
            lines = [f"**Переменные окружения** ({total} всего):\n"]
            for k in sorted(env)[:MAX]:
                v = env[k]
                display = v if len(v) <= 60 else v[:60] + "…"
                lines.append(f"- `{k}` = `{display}`")
            if total > MAX:
                lines.append(f"\n*…и ещё {total - MAX}. Используйте `/env --filter pat` для поиска.*")
            lines.append(
                "\n**Команды:** `/env VAR` • `/env VAR=val` • `/env unset VAR` • "
                "`/env --filter pat` • `/env --export`"
            )
            return "\n".join(lines)

        self.register(SlashCommand(
            "envvars",
            "Переменные окружения ОС: /envvars [VAR] [VAR=val] [unset VAR] [--filter pat] [--export]",
            env_handler,
        ))

        # ── Task 239: /template ───────────────────────────────────────────────

        _TEMPLATES: dict[str, tuple[str, str]] = {
            "class": ("MyClass.py", '''\
class {Name}:
    """Docstring for {Name}."""

    def __init__(self) -> None:
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"
'''),
            "function": ("func.py", '''\
from typing import Any


def {name}(*args: Any, **kwargs: Any) -> None:
    """Docstring for {name}."""
    raise NotImplementedError
'''),
            "dataclass": ("model.py", '''\
from dataclasses import dataclass, field
from typing import Any


@dataclass
class {Name}:
    """Data model for {Name}."""

    id: int = 0
    name: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "tags": self.tags}
'''),
            "test": ("test_module.py", '''\
"""Tests for {name}."""
from __future__ import annotations

import pytest


class Test{Name}:
    def test_basic(self) -> None:
        assert True

    def test_raises(self) -> None:
        with pytest.raises(NotImplementedError):
            raise NotImplementedError
'''),
            "cli": ("cli.py", '''\
"""CLI entry point."""
from __future__ import annotations

import argparse
import sys


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="{name}")
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''),
            "fastapi": ("app.py", '''\
"""FastAPI application."""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="{name}")


class Item(BaseModel):
    id: int
    name: str


@app.get("/")
async def root() -> dict[str, str]:
    return {{"message": "Hello from {name}"}}


@app.get("/items/{{item_id}}")
async def get_item(item_id: int) -> Item:
    return Item(id=item_id, name="example")
'''),
            "decorator": ("decorators.py", '''\
"""Custom decorators."""
from __future__ import annotations

import functools
import logging
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])
log = logging.getLogger(__name__)


def {name}(func: F) -> F:
    """Decorator: {name}."""
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        log.debug("Calling %s", func.__name__)
        result = func(*args, **kwargs)
        log.debug("Done %s", func.__name__)
        return result
    return wrapper  # type: ignore[return-value]
'''),
            "context": ("context.py", '''\
"""Context manager."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator


@contextmanager
def {name}() -> Generator[None, None, None]:
    """Context manager: {name}."""
    # setup
    try:
        yield
    finally:
        # teardown
        pass
'''),
        }

        async def template_handler(arg: str = "", **_) -> str:
            import re as _re

            raw = arg.strip()

            # /template — list all
            if not raw or raw == "list":
                names = sorted(_TEMPLATES)
                lines = [f"**Доступные шаблоны** ({len(names)}):\n"]
                for name in names:
                    default_file, content = _TEMPLATES[name]
                    loc = len(content.splitlines())
                    lines.append(f"- `{name}` — `{default_file}` ({loc} строк)")
                lines.append(
                    "\n**Использование:**\n"
                    "- `/template <имя>` — показать шаблон\n"
                    "- `/template <имя> <файл.py>` — создать файл\n"
                    "- `/template <имя> <файл.py> Name=MyClass` — с заменой"
                )
                return "\n".join(lines)

            parts = raw.split(None)
            tmpl_name = parts[0].lower()

            if tmpl_name not in _TEMPLATES:
                close = [k for k in _TEMPLATES if k.startswith(tmpl_name[:2])]
                hint = f" Возможно: {', '.join(close)}" if close else ""
                return f"❌ Шаблон `{tmpl_name}` не найден.{hint}\n\nДоступные: {', '.join(sorted(_TEMPLATES))}"

            default_file, template_content = _TEMPLATES[tmpl_name]

            # Collect substitutions: Name=Foo or name=foo from remaining parts
            output_path: str | None = None
            subs: dict[str, str] = {}
            for part in parts[1:]:
                if "=" in part and not part.startswith("/"):
                    k, _, v = part.partition("=")
                    subs[k.strip()] = v.strip()
                elif not output_path:
                    output_path = part

            # Apply substitutions to template
            content = template_content
            for k, v in subs.items():
                content = content.replace("{" + k + "}", v)

            # /template name — just show
            if output_path is None:
                return (
                    f"**Шаблон:** `{tmpl_name}` (→ `{default_file}`)\n\n"
                    f"```python\n{content}```\n\n"
                    f"*Создать файл: `/template {tmpl_name} <путь.py>`*"
                )

            p = Path(output_path)
            if p.exists():
                return f"❌ Файл уже существует: `{output_path}`. Удалите или выберите другое имя."

            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
            except Exception as e:
                return f"❌ Ошибка записи: {e}"

            loc = len(content.splitlines())
            return (
                f"✅ **Создан** `{output_path}` из шаблона `{tmpl_name}` ({loc} строк)\n\n"
                f"```python\n{content[:400]}{'…' if len(content) > 400 else ''}```"
            )

        self.register(SlashCommand(
            "scaffold",
            "Scaffolding шаблонов: /scaffold [имя] [файл] [Key=Value]",
            template_handler,
        ))

        # ── Task 240: /alias ──────────────────────────────────────────────────

        # Aliases are stored in .lidco/aliases.json as {name: command_string}
        # They are also cached in-memory on the registry for fast lookup.
        if not hasattr(self, "_aliases"):
            self._aliases: dict[str, str] = {}

        def _aliases_file() -> Path:
            return Path(".lidco") / "aliases.json"

        def _load_aliases() -> dict[str, str]:
            import json as _json
            f = _aliases_file()
            if f.exists():
                try:
                    return _json.loads(f.read_text(encoding="utf-8"))
                except Exception:
                    pass
            return {}

        def _save_aliases(data: dict[str, str]) -> None:
            import json as _json
            f = _aliases_file()
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        async def alias_handler(arg: str = "", **_) -> str:
            import re as _re

            raw = arg.strip()

            def _define(name: str, cmd: str) -> str:
                if not name or not _re.match(r"^[A-Za-z0-9_-]+$", name):
                    return f"❌ Некорректное имя псевдонима: `{name}`."
                if not cmd:
                    return "❌ Команда не может быть пустой."
                # Auto-prefix with / if missing
                if not cmd.startswith("/"):
                    cmd = "/" + cmd
                self._aliases[name] = cmd
                _save_aliases(self._aliases)
                return f"✓ Псевдоним `{name}` → `{cmd}` создан."

            # /alias — list
            if not raw or raw == "list":
                if not self._aliases:
                    return (
                        "Псевдонимы не определены.\n\n"
                        "**Создать:** `/alias <имя> <команда>` или `/alias <имя>=<команда>`\n"
                        "**Удалить:** `/alias del <имя>`"
                    )
                lines = [f"**Псевдонимы** ({len(self._aliases)}):\n"]
                for name in sorted(self._aliases):
                    lines.append(f"- `{name}` → `{self._aliases[name]}`")
                lines.append("\n**Выполнить:** `/alias run <имя>` | **Удалить:** `/alias del <имя>`")
                return "\n".join(lines)

            # /alias del name
            if raw.startswith("del "):
                name = raw[4:].strip()
                if not name:
                    return "❌ Укажите имя псевдонима: `/alias del <имя>`"
                if name not in self._aliases:
                    return f"⚠️ Псевдоним `{name}` не найден."
                del self._aliases[name]
                _save_aliases(self._aliases)
                return f"✓ Псевдоним `{name}` удалён."

            # /alias run name
            if raw.startswith("run "):
                name = raw[4:].strip()
                if not name:
                    return "❌ Укажите имя псевдонима: `/alias run <имя>`"
                if name not in self._aliases:
                    return f"⚠️ Псевдоним `{name}` не найден."
                cmd = self._aliases[name]
                return f"**Псевдоним** `{name}` → `{cmd}`\n\n*Скопируйте команду в строку ввода для выполнения.*"

            # /alias show name  (single-word lookup — old behavior)
            if raw.startswith("show "):
                name = raw[5:].strip()
                if not name:
                    return "❌ Укажите имя: `/alias show <имя>`"
                if name not in self._aliases:
                    return f"⚠️ Псевдоним `{name}` не найден."
                return f"**{name}** = `{self._aliases[name]}`"

            # /alias clear
            if raw == "clear":
                self._aliases.clear()
                _save_aliases(self._aliases)
                return "✓ Все псевдонимы удалены."

            # /alias name=/command ... — create/update (new = syntax)
            if "=" in raw and " " not in raw.split("=")[0]:
                name, _, cmd = raw.partition("=")
                return _define(name.strip(), cmd.strip())

            # /alias name command ... — create/update (old space syntax)
            parts = raw.split(None, 1)
            if len(parts) == 2:
                name, cmd = parts
                return _define(name.strip(), cmd.strip())

            # /alias name — show single alias (old behavior)
            if len(parts) == 1:
                name = parts[0]
                if name in self._aliases:
                    return f"`{name}` → `{self._aliases[name]}`"
                return f"⚠️ Псевдоним `{name}` не найден."

            return (
                "**Использование:**\n"
                "- `/alias` — список псевдонимов\n"
                "- `/alias <имя> <команда>` — создать\n"
                "- `/alias <имя>=<команда>` — создать (альтернативный синтаксис)\n"
                "- `/alias run <имя>` — показать для выполнения\n"
                "- `/alias del <имя>` — удалить\n"
                "- `/alias clear` — удалить все"
            )

        self.register(SlashCommand(
            "alias",
            "Псевдонимы команд: /alias [имя=команда] [run|del|list|clear]",
            alias_handler,
        ))

        # ── Task 241: /snippet ────────────────────────────────────────────────
        # Snippets stored in .lidco/snippets.json as:
        # {name: {code, lang, desc, created}}

        def _snippets_file() -> Path:
            return Path(".lidco") / "snippets.json"

        def _load_snippets() -> dict:
            import json as _json
            f = _snippets_file()
            if f.exists():
                try:
                    return _json.loads(f.read_text(encoding="utf-8"))
                except Exception:
                    pass
            return {}

        def _save_snippets(data: dict) -> None:
            import json as _json
            f = _snippets_file()
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        async def snippet_handler(arg: str = "", **_) -> str:
            import re as _re
            from datetime import datetime as _dt

            raw = arg.strip()
            db = _load_snippets()

            # /snippet — list all
            if not raw or raw == "list":
                if not db:
                    return (
                        "*Сниппетов нет.*\n\n"
                        "**Сохранить:** `/snippet save <имя> [--lang py] [--desc Описание]`\n"
                        "**Из файла:** `/snippet save <имя> <файл.py>`\n"
                        "**Показать:** `/snippet show <имя>`"
                    )
                lines = [f"**Сниппеты** ({len(db)}):\n"]
                for name in sorted(db):
                    s = db[name]
                    lang = s.get("lang", "")
                    desc = s.get("desc", "")
                    loc = len(s.get("code", "").splitlines())
                    tag = f"  *{desc}*" if desc else ""
                    lines.append(f"- `{name}` ({lang}, {loc} строк){tag}")
                return "\n".join(lines)

            # /snippet show <name>
            if raw.startswith("show "):
                name = raw[5:].strip()
                if name not in db:
                    return f"❌ Сниппет `{name}` не найден."
                s = db[name]
                lang = s.get("lang", "")
                desc = s.get("desc", "")
                code = s.get("code", "")
                header = f"**{name}**"
                if desc:
                    header += f"  *{desc}*"
                return f"{header}\n\n```{lang}\n{code}\n```"

            # /snippet del <name>
            if raw.startswith("del "):
                name = raw[4:].strip()
                if not name:
                    return "❌ Укажите имя: `/snippet del <имя>`"
                if name not in db:
                    return f"⚠️ Сниппет `{name}` не найден."
                del db[name]
                _save_snippets(db)
                return f"✓ Сниппет `{name}` удалён."

            # /snippet clear
            if raw == "clear":
                _save_snippets({})
                return "✓ Все сниппеты удалены."

            # /snippet export <name> <file>
            if raw.startswith("export "):
                parts = raw[7:].strip().split(None, 1)
                if len(parts) < 2:
                    return "❌ Использование: `/snippet export <имя> <файл>`"
                name, fpath = parts[0], parts[1]
                if name not in db:
                    return f"❌ Сниппет `{name}` не найден."
                p = Path(fpath)
                if p.exists():
                    return f"❌ Файл уже существует: `{fpath}`"
                p.write_text(db[name]["code"], encoding="utf-8")
                return f"✅ Сниппет `{name}` экспортирован в `{fpath}`"

            # /snippet save <name> [<file>] [--lang X] [--desc Y]
            if raw.startswith("save "):
                rest = raw[5:].strip()

                # Extract --lang
                lang = "py"
                m_lang = _re.search(r"--lang\s+(\S+)", rest)
                if m_lang:
                    lang = m_lang.group(1)
                    rest = rest[:m_lang.start()].strip() + " " + rest[m_lang.end():].strip()

                # Extract --desc
                desc = ""
                m_desc = _re.search(r"--desc\s+(.+?)(?:\s+--|$)", rest)
                if m_desc:
                    desc = m_desc.group(1).strip()
                    rest = rest[:m_desc.start()].strip() + " " + rest[m_desc.end():].strip()

                rest = rest.strip()
                parts = rest.split(None, 1)
                if not parts:
                    return "❌ Укажите имя сниппета: `/snippet save <имя>`"

                name = parts[0]
                if not _re.match(r"^[A-Za-z0-9_.-]+$", name):
                    return f"❌ Некорректное имя: `{name}`"

                code = ""
                if len(parts) > 1:
                    fpath = parts[1].strip()
                    fp = Path(fpath)
                    if fp.exists() and fp.is_file():
                        try:
                            code = fp.read_text(encoding="utf-8")
                            lang = fp.suffix.lstrip(".") or lang
                        except Exception as e:
                            return f"❌ Ошибка чтения файла: {e}"
                    else:
                        # Treat as inline code
                        code = fpath

                if not code.strip():
                    return (
                        "❌ Нет кода для сохранения.\n"
                        "Использование: `/snippet save <имя> <файл>` или передайте код"
                    )

                db[name] = {
                    "code": code,
                    "lang": lang,
                    "desc": desc,
                    "created": _dt.now().isoformat(timespec="seconds"),
                }
                _save_snippets(db)
                loc = len(code.splitlines())
                return f"✅ Сниппет `{name}` сохранён ({loc} строк, {lang})"

            return (
                "**Использование:**\n"
                "- `/snippet` — список сниппетов\n"
                "- `/snippet save <имя> <файл|код> [--lang py] [--desc ...]` — сохранить\n"
                "- `/snippet show <имя>` — показать\n"
                "- `/snippet del <имя>` — удалить\n"
                "- `/snippet export <имя> <файл>` — экспортировать\n"
                "- `/snippet clear` — удалить все"
            )

        self.register(SlashCommand(
            "snippet",
            "Сниппеты кода: /snippet [save|show|del|export|clear|list]",
            snippet_handler,
        ))

        # ── Task 242: /todo ───────────────────────────────────────────────────
        # Todos stored in .lidco/todos.json as list of:
        # {id, text, done, priority, created}

        def _todos_file() -> Path:
            return Path(".lidco") / "todos.json"

        def _load_todos() -> list:
            import json as _json
            f = _todos_file()
            if f.exists():
                try:
                    return _json.loads(f.read_text(encoding="utf-8"))
                except Exception:
                    pass
            return []

        def _save_todos(data: list) -> None:
            import json as _json
            f = _todos_file()
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        async def todo_handler(arg: str = "", **_) -> str:
            import re as _re
            from datetime import datetime as _dt

            raw = arg.strip()
            todos = _load_todos()

            def _next_id() -> int:
                return max((t["id"] for t in todos), default=0) + 1

            def _render(todo_list: list, title: str = "TODO") -> str:
                if not todo_list:
                    return f"*{title}: нет задач.*"
                lines = [f"**{title}** ({len(todo_list)} задач):\n"]
                for t in todo_list:
                    check = "✅" if t.get("done") else "☐"
                    pri = t.get("priority", "")
                    pri_tag = f" [{pri}]" if pri else ""
                    lines.append(f"{check} **#{t['id']}** {t['text']}{pri_tag}")
                return "\n".join(lines)

            # /todo — list pending
            if not raw or raw == "list":
                pending = [t for t in todos if not t.get("done")]
                done_count = len(todos) - len(pending)
                result = _render(pending, "TODO")
                if done_count:
                    result += f"\n\n*+ {done_count} выполнено. Используйте `/todo all` для просмотра.*"
                if not pending and not todos:
                    result = (
                        "*Список задач пуст.*\n\n"
                        "**Добавить:** `/todo Описание задачи`\n"
                        "**Приоритет:** `/todo !high Срочная задача`"
                    )
                return result

            # /todo all
            if raw == "all":
                return _render(todos, "Все задачи")

            # /todo done <id>
            if raw.startswith("done "):
                try:
                    tid = int(raw[5:].strip())
                except ValueError:
                    return "❌ Укажите номер задачи: `/todo done <номер>`"
                for t in todos:
                    if t["id"] == tid:
                        t["done"] = True
                        _save_todos(todos)
                        return f"✅ Задача **#{tid}** выполнена: *{t['text']}*"
                return f"⚠️ Задача **#{tid}** не найдена."

            # /todo del <id>
            if raw.startswith("del "):
                try:
                    tid = int(raw[4:].strip())
                except ValueError:
                    return "❌ Укажите номер задачи: `/todo del <номер>`"
                before = len(todos)
                todos = [t for t in todos if t["id"] != tid]
                if len(todos) == before:
                    return f"⚠️ Задача **#{tid}** не найдена."
                _save_todos(todos)
                return f"✓ Задача **#{tid}** удалена."

            # /todo clear
            if raw == "clear":
                _save_todos([])
                return "✓ Список задач очищен."

            # /todo undone <id>
            if raw.startswith("undone "):
                try:
                    tid = int(raw[7:].strip())
                except ValueError:
                    return "❌ Укажите номер задачи: `/todo undone <номер>`"
                for t in todos:
                    if t["id"] == tid:
                        t["done"] = False
                        _save_todos(todos)
                        return f"↩️ Задача **#{tid}** возвращена в список."
                return f"⚠️ Задача **#{tid}** не найдена."

            # /todo stats
            if raw == "stats":
                total = len(todos)
                done = sum(1 for t in todos if t.get("done"))
                pending = total - done
                pct = int(done / total * 100) if total else 0
                bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                return (
                    f"**TODO статистика**\n\n"
                    f"Всего: {total} | Выполнено: {done} | Ожидает: {pending}\n"
                    f"Прогресс: [{bar}] {pct}%"
                )

            # /todo search <query>
            if raw.startswith("search "):
                q = raw[7:].strip().lower()
                matches = [t for t in todos if q in t["text"].lower()]
                return _render(matches, f"Поиск: {q}")

            # /todo <text> — add new
            # Priority prefix: !high !med !low
            priority = ""
            text = raw
            m_pri = _re.match(r"^!(high|med|low)\s+(.+)", raw, _re.IGNORECASE)
            if m_pri:
                priority = m_pri.group(1).upper()
                text = m_pri.group(2).strip()

            if not text:
                return "❌ Укажите текст задачи."

            new_todo = {
                "id": _next_id(),
                "text": text,
                "done": False,
                "priority": priority,
                "created": _dt.now().isoformat(timespec="seconds"),
            }
            todos.append(new_todo)
            _save_todos(todos)
            pri_tag = f" [{priority}]" if priority else ""
            return f"✓ Задача **#{new_todo['id']}** добавлена: *{text}*{pri_tag}"

        self.register(SlashCommand(
            "todo",
            "Список задач: /todo [текст] [done|del|undone|stats|search|clear|all]",
            todo_handler,
        ))

        # ── Task 243: /timer ──────────────────────────────────────────────────
        # In-memory session timers: {name: start_ts}
        if not hasattr(self, "_timers"):
            self._timers: dict[str, float] = {}

        async def timer_handler(arg: str = "", **_) -> str:
            import time as _time
            import re as _re

            raw = arg.strip()

            def _fmt_elapsed(seconds: float) -> str:
                s = int(seconds)
                h, rem = divmod(s, 3600)
                m, sc = divmod(rem, 60)
                if h:
                    return f"{h}ч {m:02d}м {sc:02d}с"
                if m:
                    return f"{m}м {sc:02d}с"
                return f"{sc}с"

            # /timer — list active timers
            if not raw or raw == "list":
                if not self._timers:
                    return (
                        "*Нет активных таймеров.*\n\n"
                        "**Запустить:** `/timer start [имя]`\n"
                        "**Остановить:** `/timer stop [имя]`\n"
                        "**Статус:** `/timer status [имя]`"
                    )
                now = _time.monotonic()
                lines = [f"**Активные таймеры** ({len(self._timers)}):\n"]
                for name, start in sorted(self._timers.items()):
                    elapsed = now - start
                    lines.append(f"- `{name}` — {_fmt_elapsed(elapsed)}")
                return "\n".join(lines)

            # /timer start [name]
            if raw == "start" or raw.startswith("start "):
                name = raw[6:].strip() if raw.startswith("start ") else "default"
                if not name:
                    name = "default"
                if name in self._timers:
                    elapsed = _time.monotonic() - self._timers[name]
                    return f"⚠️ Таймер `{name}` уже запущен ({_fmt_elapsed(elapsed)} назад)."
                self._timers[name] = _time.monotonic()
                return f"▶️ Таймер `{name}` запущен."

            # /timer stop [name]
            if raw == "stop" or raw.startswith("stop "):
                name = raw[5:].strip() if raw.startswith("stop ") else "default"
                if not name:
                    name = "default"
                if name not in self._timers:
                    return f"⚠️ Таймер `{name}` не найден."
                elapsed = _time.monotonic() - self._timers.pop(name)
                return f"⏹️ Таймер `{name}` остановлен. Прошло: **{_fmt_elapsed(elapsed)}**"

            # /timer status [name]
            if raw == "status" or raw.startswith("status "):
                name = raw[7:].strip() if raw.startswith("status ") else "default"
                if not name:
                    name = "default"
                if name not in self._timers:
                    return f"⚠️ Таймер `{name}` не найден."
                elapsed = _time.monotonic() - self._timers[name]
                return f"⏱️ Таймер `{name}`: **{_fmt_elapsed(elapsed)}**"

            # /timer reset [name]
            if raw == "reset" or raw.startswith("reset "):
                name = raw[6:].strip() if raw.startswith("reset ") else "default"
                if not name:
                    name = "default"
                self._timers[name] = _time.monotonic()
                return f"🔄 Таймер `{name}` перезапущен."

            # /timer clear
            if raw == "clear":
                count = len(self._timers)
                self._timers.clear()
                return f"✓ Удалено {count} таймер(ов)."

            # /timer lap [name] — show elapsed without stopping
            if raw == "lap" or raw.startswith("lap "):
                name = raw[4:].strip() if raw.startswith("lap ") else "default"
                if not name:
                    name = "default"
                if name not in self._timers:
                    return f"⚠️ Таймер `{name}` не найден."
                elapsed = _time.monotonic() - self._timers[name]
                return f"⏱️ Lap `{name}`: {_fmt_elapsed(elapsed)}"

            return (
                "**Использование `/timer`:**\n"
                "- `/timer start [имя]` — запустить таймер\n"
                "- `/timer stop [имя]` — остановить и показать время\n"
                "- `/timer status [имя]` — текущее время\n"
                "- `/timer lap [имя]` — промежуточный результат\n"
                "- `/timer reset [имя]` — перезапустить\n"
                "- `/timer list` — все активные таймеры\n"
                "- `/timer clear` — удалить все"
            )

        self.register(SlashCommand(
            "timer",
            "Таймер рабочей сессии: /timer [start|stop|status|lap|reset|list|clear] [имя]",
            timer_handler,
        ))

        # ── Q38: /mcp ─────────────────────────────────────────────────────────

        async def mcp_handler(arg: str = "", **_: Any) -> str:
            """Manage MCP server connections.

            Subcommands:
              /mcp                 — list all configured servers and their status
              /mcp status          — same as /mcp
              /mcp status <name>   — status for one server
              /mcp reconnect <name>— force-reconnect a server
              /mcp tools [name]    — list available MCP tools
            """
            if not registry._session:
                return "Session not initialized."

            manager = getattr(registry._session, "mcp_manager", None)
            if manager is None:
                return (
                    "MCP integration is not active.\n\n"
                    "Add servers to `.lidco/mcp.json` to get started:\n"
                    "```json\n"
                    '{"servers": [{"name": "myserver", "command": ["npx", "my-mcp-server"]}]}\n'
                    "```"
                )

            raw = (arg or "").strip()
            parts = raw.split(maxsplit=1) if raw else []
            sub = parts[0].lower() if parts else "status"
            rest = parts[1] if len(parts) > 1 else ""

            # ── /mcp status [name] ────────────────────────────────────────────
            if sub in ("status", ""):
                statuses = manager.get_status(rest.strip() or None)
                if not statuses:
                    return "No MCP servers configured." if not rest else f"Server `{rest}` not found."

                lines = ["**MCP Servers**\n"]
                for name, st in statuses.items():
                    icon = "✓" if st.connected else "✗"
                    connected_str = (
                        f"connected at {st.connected_at.strftime('%H:%M:%S')}"
                        if st.connected and st.connected_at
                        else "not connected"
                    )
                    lines.append(
                        f"- **{name}** [{st.transport}] {icon} {connected_str}"
                        + (f" — {st.tool_count} tool(s)" if st.connected else "")
                        + (f"\n  Error: {st.last_error}" if st.last_error else "")
                    )
                return "\n".join(lines)

            # ── /mcp tools [name] ─────────────────────────────────────────────
            if sub == "tools":
                all_schemas = manager.all_tool_schemas()
                if rest:
                    schemas = all_schemas.get(rest, [])
                    if not schemas:
                        return f"No tools found for server `{rest}`."
                    lines = [f"**MCP tools from `{rest}`**\n"]
                    for s in schemas:
                        lines.append(f"- `{s.name}` — {s.description or '(no description)'}")
                    return "\n".join(lines)

                if not all_schemas:
                    return "No MCP tools available (no servers connected)."
                lines = ["**MCP Tools**\n"]
                for server_name, schemas in all_schemas.items():
                    lines.append(f"**{server_name}** ({len(schemas)} tool(s))")
                    for s in schemas[:5]:
                        lines.append(f"  - `mcp__{server_name}__{s.name}` — {s.description or ''}")
                    if len(schemas) > 5:
                        lines.append(f"  … and {len(schemas) - 5} more")
                return "\n".join(lines)

            # ── /mcp reconnect <name> ─────────────────────────────────────────
            if sub == "reconnect":
                if not rest:
                    return "**Usage:** `/mcp reconnect <server-name>`"
                mcp_config = getattr(registry._session, "mcp_config", None)
                if mcp_config is None:
                    return "MCP config not available."
                entry = mcp_config.get_server(rest)
                if entry is None:
                    return f"Server `{rest}` not found in config."
                # Run reconnect in background to avoid blocking the REPL
                import asyncio
                asyncio.ensure_future(manager.reconnect(rest, entry))
                return f"Reconnecting to `{rest}`…"

            return (
                "**Usage:** `/mcp [status|tools|reconnect] [name]`\n\n"
                "- `/mcp` — list all MCP servers\n"
                "- `/mcp status <name>` — status for one server\n"
                "- `/mcp tools [name]` — list MCP tools\n"
                "- `/mcp reconnect <name>` — force-reconnect a server"
            )

        self.register(SlashCommand("mcp", "Manage MCP server connections", mcp_handler))

        # ── Q41 — UX Completeness (Tasks 276–285) ────────────────────────────

        # Task 276 (merges Task 161): /compact — keep last N messages OR LLM summarize
        async def compact_handler(arg: str = "", **_: Any) -> str:
            """/compact [N | focus] — keep last N messages, or LLM-summarize with optional focus."""
            session = registry._session
            orch = getattr(session, "orchestrator", None)
            if orch is None:
                return "No active session."
            history = getattr(orch, "_conversation_history", None) or []

            # ── Numeric arg: truncate mode (Task 161 behaviour) ──────────────
            arg_stripped = arg.strip()
            if arg_stripped == "" or arg_stripped.lstrip("-").isdigit():
                if not history:
                    return "История разговора пуста — нечего сжимать."
                _DEFAULT_KEEP = 6
                keep = _DEFAULT_KEEP
                if arg_stripped:
                    try:
                        keep = int(arg_stripped)
                    except ValueError:
                        return f"Неверный аргумент: `{arg_stripped}`. Использование: `/compact [N]` (N — количество сообщений)."
                keep = max(2, keep)
                if len(history) <= keep:
                    return f"История уже короткая ({len(history)} сообщений) — нечего удалять."
                removed = len(history) - keep
                compacted = history[-keep:]
                orch.restore_history(compacted)
                return f"Оставлено {keep} сообщений, удалено {removed}."

            # ── Non-numeric arg: validate — must start with "--llm" ──────────────
            if not arg_stripped.startswith("--llm"):
                return f"Неверный аргумент: `{arg_stripped}`. Использование: `/compact [N]` или `/compact --llm [focus]`."

            # ── LLM summarisation mode (Task 276) ────────────────────────────
            if not history:
                return "Conversation history is empty — nothing to compact."
            focus_hint = arg_stripped[len("--llm"):].strip()
            system = (
                "You are a conversation summarizer. "
                "Compress the following conversation history into a concise summary "
                "that preserves ALL important decisions, code snippets, file paths, "
                "error messages, and conclusions. "
                "Output only the summary — no preamble."
            )
            if focus_hint:
                system += f" Pay special attention to: {focus_hint}."

            history_text = "\n".join(
                f"[{m.get('role','?')}]: {str(m.get('content',''))[:300]}"
                for m in history[-40:]
            )
            try:
                llm = getattr(session, "llm", None)
                if llm is None:
                    return "LLM not available."
                resp = await llm.complete(
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": f"Summarize:\n\n{history_text}"},
                    ],
                    model=None,
                    max_tokens=800,
                )
                summary = resp.content if hasattr(resp, "content") else str(resp)
                orch._conversation_history = [
                    {"role": "assistant", "content": f"[Compacted history]\n\n{summary}"}
                ]
                turns_before = len(history)
                return (
                    f"History compacted: {turns_before} messages → 1 summary.\n\n"
                    f"**Summary:**\n{summary}"
                )
            except Exception as exc:
                return f"Compact failed: {exc}"

        self.register(SlashCommand("compact", "Compress conversation history (N=keep last N, text=LLM summarize)", compact_handler))

        # Task 277: /context — visual token gauge
        async def context_handler(arg: str = "", **_: Any) -> str:
            """/context [tree] — visual context window usage gauge or section tree."""
            session = registry._session
            config = getattr(session, "config", None)
            budget = getattr(session, "token_budget", None)

            # Task 387: /context tree — parse context into sections with token estimates
            if arg.strip().lower() == "tree":
                import re as _re
                orch = getattr(session, "orchestrator", None)
                history = getattr(orch, "_conversation_history", []) if orch else []
                # Build a combined context string from system/assistant messages
                context_str = ""
                for m in history:
                    role = m.get("role", "")
                    content = str(m.get("content", ""))
                    if role in ("system", "assistant"):
                        context_str += content + "\n"

                # If no history, try session context attribute
                if not context_str:
                    context_str = getattr(session, "context", "") or ""

                total_limit = 128_000
                if config is not None:
                    try:
                        limit_cfg = int(getattr(config.agents, "context_window", 0))
                        if limit_cfg > 0:
                            total_limit = limit_cfg
                    except (TypeError, ValueError):
                        pass

                # Parse by ## headings
                sections: list[tuple[str, str]] = []
                current_title = "Preamble"
                current_body: list[str] = []
                for line in context_str.splitlines():
                    m = _re.match(r"^##\s+(.+)$", line)
                    if m:
                        sections.append((current_title, "\n".join(current_body)))
                        current_title = m.group(1).strip()
                        current_body = []
                    else:
                        current_body.append(line)
                sections.append((current_title, "\n".join(current_body)))

                # Filter empty
                sections = [(t, b) for t, b in sections if b.strip()]

                total_chars = sum(len(b) for _, b in sections)
                total_toks = max(total_chars // 4, 1)

                try:
                    from rich.tree import Tree as _Tree
                    from rich.console import Console as _Con
                    import io as _io
                    tree = _Tree(f"[bold cyan]Context[/bold cyan] [{total_toks} tok / {total_limit // 1000}k limit]")
                    for title, body in sections:
                        toks = len(body) // 4
                        pct_sec = int(toks / total_limit * 100) if total_limit else 0
                        tree.add(f"[dim]##[/dim] {title}  [yellow][{toks} tok, {pct_sec}%][/yellow]")
                    buf = _io.StringIO()
                    c = _Con(file=buf, highlight=False)
                    c.print(tree)
                    return buf.getvalue().rstrip()
                except Exception:
                    lines = [f"**Context tree** ({total_toks} tokens estimated)\n"]
                    for title, body in sections:
                        toks = len(body) // 4
                        lines.append(f"  ## {title}  [{toks} tok]")
                    return "\n".join(lines)

            # Default: gauge view
            # Gather stats
            used = 0
            prompt_tokens = 0
            completion_tokens = 0
            total_limit = 128_000

            if budget is not None:
                stats = getattr(budget, "_stats", None)
                if stats is not None:
                    used = getattr(stats, "total_tokens", 0)
                    prompt_tokens = getattr(stats, "prompt_tokens", 0)
                    completion_tokens = getattr(stats, "completion_tokens", 0)

            if config is not None:
                try:
                    limit_cfg = int(getattr(config.agents, "context_window", 0))
                    if limit_cfg > 0:
                        total_limit = limit_cfg
                except (TypeError, ValueError):
                    pass

            if used == 0 and budget is not None:
                # Fallback: count history tokens
                orch = getattr(session, "orchestrator", None)
                if orch:
                    history = getattr(orch, "_conversation_history", [])
                    used = sum(len(str(m.get("content", ""))) // 4 for m in history)

            pct = min(int(used / total_limit * 100), 100) if total_limit > 0 else 0

            # Build bar (20 chars wide)
            filled = pct * 20 // 100
            bar_full = "█" * filled + "░" * (20 - filled)
            if pct >= 80:
                bar_color = "red"
            elif pct >= 60:
                bar_color = "yellow"
            else:
                bar_color = "green"

            def _fmt(n: int) -> str:
                return f"{n / 1000:.1f}k" if n >= 1000 else str(n)

            lines = [
                f"**Context Window Usage**\n",
                f"`[{bar_full}]` {pct}%",
                f"",
                f"Used:  {_fmt(used)} / {_fmt(total_limit)} tokens",
            ]
            if prompt_tokens or completion_tokens:
                lines.append(f"Prompt:     {_fmt(prompt_tokens)}")
                lines.append(f"Completion: {_fmt(completion_tokens)}")

            orch = getattr(session, "orchestrator", None)
            if orch:
                history = getattr(orch, "_conversation_history", [])
                lines.append(f"Messages:   {len(history)}")

            if pct >= 80:
                lines.append(f"\n⚠️  Context at {pct}% — consider `/compact` to free space.")
            lines.append("\nTip: `/context tree` — show sections with token breakdown")
            return "\n".join(lines)

        self.register(SlashCommand("context", "Show context window usage gauge", context_handler))

        # Task 278: /mention — inject file into next turn
        # _mentions stored on registry
        registry._mentions: list[str] = []

        async def mention_handler(arg: str = "", **_: Any) -> str:
            """/mention <file> — inject file content into next message context."""
            if not arg.strip():
                if not registry._mentions:
                    return "No files mentioned. Usage: `/mention src/foo.py`"
                lines = ["**Mentioned files (injected into next turn):**\n"]
                for f in registry._mentions:
                    lines.append(f"  · {f}")
                return "\n".join(lines)

            path_str = arg.strip()
            from pathlib import Path as _Path
            p = _Path(path_str)
            if not p.exists():
                return f"File not found: `{path_str}`"
            if path_str not in registry._mentions:
                registry._mentions.append(path_str)
            return f"File `{path_str}` will be injected into your next message."

        self.register(SlashCommand("mention", "Inject a file into the next agent turn", mention_handler))

        # Task 279: /model — switch model in-session
        async def model_handler(arg: str = "", **_: Any) -> str:
            """/model [name] — show or switch current model."""
            session = registry._session
            config = getattr(session, "config", None)
            llm = getattr(session, "llm", None)

            if not arg.strip():
                current = getattr(config.llm, "default_model", "?") if config else "?"
                return f"**Current model:** `{current}`\n\nUsage: `/model <name>` — e.g. `/model claude-opus-4-6`"

            new_model = arg.strip()
            if config is not None:
                config.llm.default_model = new_model
            if llm is not None and hasattr(llm, "set_default_model"):
                llm.set_default_model(new_model)
            return f"Model switched to `{new_model}` — takes effect on next request."

        self.register(SlashCommand("model", "Show or switch the current LLM model", model_handler))

        # Task 280: /theme — color theme
        _THEMES = {
            "dark":       {"bg": "grey7",    "accent": "cyan",   "label": "Dark (default)"},
            "light":      {"bg": "grey93",   "accent": "blue",   "label": "Light"},
            "solarized":  {"bg": "grey19",   "accent": "yellow", "label": "Solarized"},
            "nord":       {"bg": "grey15",   "accent": "steel_blue1", "label": "Nord"},
            "monokai":    {"bg": "grey11",   "accent": "chartreuse1", "label": "Monokai"},
        }
        registry._theme: str = "dark"

        async def theme_handler(arg: str = "", **_: Any) -> str:
            """/theme [name] — show or set the color theme."""
            if not arg.strip():
                lines = ["**Available themes:**\n"]
                for name, cfg in _THEMES.items():
                    marker = " ← current" if name == registry._theme else ""
                    lines.append(f"  · `{name}` — {cfg['label']}{marker}")
                lines.append("\nUsage: `/theme <name>`")
                return "\n".join(lines)

            name = arg.strip().lower()
            if name not in _THEMES:
                available = ", ".join(f"`{t}`" for t in _THEMES)
                return f"Unknown theme `{name}`. Available: {available}"

            registry._theme = name
            cfg = _THEMES[name]
            return (
                f"Theme set to **{cfg['label']}**. "
                f"Accent: `{cfg['accent']}`, Background hint: `{cfg['bg']}`.\n"
                "_(Full theme support requires terminal restart — accent colors applied immediately.)_"
            )

        self.register(SlashCommand("theme", "Show or set color theme", theme_handler))

        # Task 281: /add-dir — extend file access scope
        registry._extra_dirs: list[str] = []

        async def adddir_handler(arg: str = "", **_: Any) -> str:
            """/add-dir [path] — add an external directory to the session scope."""
            if not arg.strip():
                if not registry._extra_dirs:
                    return "No extra directories added. Usage: `/add-dir ../backend`"
                lines = ["**Extra directories in scope:**\n"]
                for d in registry._extra_dirs:
                    lines.append(f"  · {d}")
                return "\n".join(lines)

            from pathlib import Path as _Path
            path_str = arg.strip()
            p = _Path(path_str).resolve()
            if not p.exists():
                return f"Directory not found: `{path_str}`"
            if not p.is_dir():
                return f"`{path_str}` is not a directory."
            resolved = str(p)
            if resolved not in registry._extra_dirs:
                registry._extra_dirs.append(resolved)
                return f"Added `{resolved}` to session scope."
            return f"`{resolved}` is already in scope."

        self.register(SlashCommand("add-dir", "Add an external directory to session scope", adddir_handler))

        # Task 283: /checkpoint — manage file checkpoints
        registry._checkpoint_mgr: Any = None  # set by app.py after wiring

        async def checkpoint_handler(arg: str = "", **_: Any) -> str:
            """/checkpoint [list|undo N] — manage pre-write checkpoints."""
            from lidco.cli.checkpoint import CheckpointManager
            mgr = registry._checkpoint_mgr
            if mgr is None:
                return "Checkpoint manager not initialized."

            parts = arg.strip().split()
            sub = parts[0].lower() if parts else "list"

            if sub == "list":
                count = mgr.count()
                if count == 0:
                    return "No checkpoints stored."
                recent = mgr.peek(5)
                lines = [f"**Checkpoints: {count} stored (last 5):**\n"]
                for i, cp in enumerate(recent, 1):
                    existed = "modified" if cp.existed else "created"
                    lines.append(f"  {i}. `{cp.path}` ({existed})")
                return "\n".join(lines)

            if sub == "undo":
                n = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
                restored = mgr.restore(n)
                if not restored:
                    return "Nothing to undo."
                return f"Restored {len(restored)} file(s): " + ", ".join(f"`{p}`" for p in restored)

            if sub == "clear":
                mgr.clear()
                return "All checkpoints cleared."

            return (
                "**Usage:** `/checkpoint [list|undo [N]|clear]`\n\n"
                "- `/checkpoint` or `/checkpoint list` — show stored checkpoints\n"
                "- `/checkpoint undo [N]` — restore last N file writes (default: 1)\n"
                "- `/checkpoint clear` — discard all checkpoints"
            )

        self.register(SlashCommand("checkpoint", "Manage pre-write file checkpoints", checkpoint_handler))

        # Task 285: /session — save/load/list sessions
        registry._session_store: Any = None  # set lazily

        async def session_handler(arg: str = "", **_: Any) -> str:
            """/session [save [id]|list [--query Q] [--since Nd]|load <id>|delete <id>|rename <n>] — manage sessions."""
            from lidco.cli.session_store import SessionStore
            if registry._session_store is None:
                registry._session_store = SessionStore()
            store: "SessionStore" = registry._session_store

            parts = arg.strip().split(maxsplit=1)
            sub = parts[0].lower() if parts else "list"
            rest = parts[1].strip() if len(parts) > 1 else ""

            if sub == "list":
                # Task 384: /session list [--query <text>] [--since <Nd>]
                query = ""
                since_days: "int | None" = None
                rest_parts = rest.split()
                i = 0
                while i < len(rest_parts):
                    tok = rest_parts[i]
                    if tok == "--query" and i + 1 < len(rest_parts):
                        query = rest_parts[i + 1]
                        i += 2
                    elif tok == "--since" and i + 1 < len(rest_parts):
                        raw = rest_parts[i + 1]
                        try:
                            since_days = int(raw.rstrip("d"))
                        except ValueError:
                            return f"Invalid --since value: `{raw}`. Use e.g. `7d` or `7`."
                        i += 2
                    else:
                        i += 1

                if query or since_days is not None:
                    results = store.search(query=query, since_days=since_days)
                    if not results:
                        return "No sessions found matching your criteria."
                    try:
                        from rich.table import Table as _Table
                        from rich.console import Console as _Con
                        import io as _io
                        t = _Table(show_header=True, header_style="bold cyan")
                        t.add_column("ID", style="dim", no_wrap=True)
                        t.add_column("Date")
                        t.add_column("Msgs", justify="right")
                        t.add_column("Preview")
                        for s in results:
                            ts = s["saved_at"][:19].replace("T", " ") if s["saved_at"] else "?"
                            t.add_row(s["session_id"], ts, str(s["message_count"]), s["first_user_message"][:60])
                        buf = _io.StringIO()
                        c = _Con(file=buf, highlight=False)
                        c.print(t)
                        return buf.getvalue().rstrip()
                    except Exception:
                        lines = ["**Sessions matching criteria:**\n"]
                        for s in results:
                            ts = s["saved_at"][:19].replace("T", " ") if s["saved_at"] else "?"
                            lines.append(f"  · `{s['session_id']}` — {ts} · {s['first_user_message'][:60]}")
                        return "\n".join(lines)

                sessions = store.list_sessions()
                if not sessions:
                    return "No saved sessions. Use `/session save` to save the current session."
                lines = ["**Saved sessions:**\n"]
                for s in sessions:
                    ts = s["saved_at"][:19].replace("T", " ") if s["saved_at"] else "?"
                    name_tag = f" ({s['metadata'].get('name')})" if s.get("metadata", {}).get("name") else ""
                    lines.append(f"  · `{s['session_id']}`{name_tag} — {ts} ({s['message_count']} messages)")
                return "\n".join(lines)

            if sub == "save":
                session = registry._session
                orch = getattr(session, "orchestrator", None)
                history = getattr(orch, "_conversation_history", []) if orch else []
                sid = store.save(history, session_id=rest or None)
                return f"Session saved as `{sid}` ({len(history)} messages)."

            if sub == "load":
                if not rest:
                    return "Usage: `/session load <session-id>`"
                data = store.load(rest)
                if data is None:
                    return f"Session `{rest}` not found."
                session = registry._session
                orch = getattr(session, "orchestrator", None)
                if orch is None:
                    return "No active orchestrator to load into."
                orch._conversation_history = data.get("history", [])
                count = len(orch._conversation_history)
                return f"Session `{rest}` loaded — {count} messages restored."

            if sub == "delete":
                if not rest:
                    return "Usage: `/session delete <session-id>`"
                if store.delete(rest):
                    return f"Session `{rest}` deleted."
                return f"Session `{rest}` not found."

            # Task 383: /session rename <new-name>
            if sub == "rename":
                if not rest:
                    return "Usage: `/session rename <new-name>`"
                session = registry._session
                orch = getattr(session, "orchestrator", None)
                history = getattr(orch, "_conversation_history", []) if orch else []
                # Save/update with new name metadata
                current_id = getattr(registry, "_current_session_id", None)
                meta: dict[str, Any] = {"name": rest}
                sid = store.save(history, session_id=current_id, metadata=meta)
                registry._current_session_id = sid
                return f"Session renamed to `{rest}` (saved as `{sid}`)."

            return (
                "**Usage:** `/session [save [id]|list [--query Q] [--since Nd]|load <id>|delete <id>|rename <n>]`\n\n"
                "- `/session save [id]` — save current conversation\n"
                "- `/session list` — list saved sessions\n"
                "- `/session list --query auth` — search sessions by content\n"
                "- `/session list --since 7d` — sessions from last 7 days\n"
                "- `/session load <id>` — restore a saved session\n"
                "- `/session delete <id>` — delete a saved session\n"
                "- `/session rename <name>` — rename current session"
            )

        self.register(SlashCommand("session", "Save, load, and manage conversation sessions", session_handler))

        # ── Q57 Task 382: /fork — session forking ────────────────────────────
        registry._current_session_id: "str | None" = None
        registry._fork_parent_id: "str | None" = None

        async def fork_handler(arg: str = "", **_: Any) -> str:
            """/fork [name] | back — fork current session or return to parent."""
            from lidco.cli.session_store import SessionStore
            if registry._session_store is None:
                registry._session_store = SessionStore()
            store: "SessionStore" = registry._session_store

            session = registry._session
            orch = getattr(session, "orchestrator", None)
            history = getattr(orch, "_conversation_history", []) if orch else []

            parts = arg.strip().split(maxsplit=1)
            sub = parts[0].lower() if parts else ""
            rest = parts[1].strip() if len(parts) > 1 else parts[0].strip() if parts else ""

            if sub == "back":
                parent_id = registry._fork_parent_id
                if not parent_id:
                    return "No parent session to return to."
                data = store.load(parent_id)
                if data is None:
                    return f"Parent session `{parent_id}` no longer exists."
                if orch is not None:
                    orch._conversation_history = data.get("history", [])
                registry._current_session_id = parent_id
                registry._fork_parent_id = None
                return f"Returned to parent session `{parent_id}` ({len(data.get('history', []))} messages)."

            # Save current history as parent
            fork_name = arg.strip() or None
            parent_id = store.save(history, session_id=registry._current_session_id)
            registry._current_session_id = parent_id

            fork_id = store.fork(parent_id, fork_name=fork_name)
            if fork_id is None:
                return "Failed to create fork."

            # Load fork into current conversation
            fork_data = store.load(fork_id)
            if fork_data and orch is not None:
                orch._conversation_history = fork_data.get("history", [])

            registry._fork_parent_id = parent_id
            registry._current_session_id = fork_id
            name_str = f" (named `{fork_name}`)" if fork_name else ""
            return (
                f"Forked from `{parent_id}` → new fork `{fork_id}`{name_str}.\n"
                f"Use `/fork back` to return to the parent session."
            )

        self.register(SlashCommand("fork", "Fork current session into a branch", fork_handler))

        # ── Q57 Task 385: /profile — workspace profiles ───────────────────────
        registry._active_profile: "str | None" = None

        async def profile_handler(arg: str = "", **_: Any) -> str:
            """/profile [list|use <name>|save <name>|delete <name>] — manage workspace profiles."""
            from lidco.core.profiles import ProfileLoader
            loader = ProfileLoader()
            project_dir = None
            try:
                from pathlib import Path as _Path
                project_dir = _Path.cwd()
            except Exception:
                pass

            parts = arg.strip().split(maxsplit=1)
            sub = parts[0].lower() if parts else "list"
            rest = parts[1].strip() if len(parts) > 1 else ""

            if sub == "list" or not arg.strip():
                names = loader.list_profiles(project_dir)
                if not names:
                    return "No profiles available."
                lines = ["**Available profiles:**\n"]
                for n in names:
                    marker = " ← active" if n == registry._active_profile else ""
                    desc = loader.load(n, project_dir)
                    desc_str = desc.get("description", "") if desc else ""
                    lines.append(f"  · `{n}`{marker}" + (f" — {desc_str}" if desc_str else ""))
                lines.append("\nUsage: `/profile use <name>`")
                return "\n".join(lines)

            if sub == "use":
                if not rest:
                    return "Usage: `/profile use <name>`"
                data = loader.load(rest, project_dir)
                if data is None:
                    return f"Profile `{rest}` not found. Use `/profile list` to see available profiles."
                # Apply agent/llm settings
                session = registry._session
                config = getattr(session, "config", None)
                if config is not None:
                    if "agents" in data and isinstance(data["agents"], dict):
                        for k, v in data["agents"].items():
                            if hasattr(config.agents, k):
                                try:
                                    setattr(config.agents, k, v)
                                except Exception:
                                    pass
                    if "llm" in data and isinstance(data["llm"], dict):
                        for k, v in data["llm"].items():
                            if hasattr(config.llm, k):
                                try:
                                    setattr(config.llm, k, v)
                                except Exception:
                                    pass
                registry._active_profile = rest
                desc_str = data.get("description", rest)
                return f"Profile `{rest}` activated ({desc_str})."

            if sub == "save":
                if not rest:
                    return "Usage: `/profile save <name>`"
                session = registry._session
                config = getattr(session, "config", None)
                data: "dict[str, Any]" = {"name": rest}
                if config is not None:
                    data["agents"] = {
                        "default": config.agents.default,
                        "auto_review": config.agents.auto_review,
                        "auto_plan": config.agents.auto_plan,
                    }
                    data["llm"] = {
                        "default_model": config.llm.default_model,
                        "temperature": config.llm.temperature,
                    }
                try:
                    path = loader.save(rest, data, project_dir)
                    return f"Profile `{rest}` saved to `{path}`."
                except Exception as exc:
                    return f"Failed to save profile: {exc}"

            if sub == "delete":
                if not rest:
                    return "Usage: `/profile delete <name>`"
                if loader.delete(rest, project_dir):
                    if registry._active_profile == rest:
                        registry._active_profile = None
                    return f"Profile `{rest}` deleted."
                return f"Profile `{rest}` not found (built-ins cannot be deleted)."

            return (
                "**Usage:** `/profile [list|use <name>|save <name>|delete <name>]`\n\n"
                "- `/profile list` — show available profiles\n"
                "- `/profile use frontend` — activate a profile\n"
                "- `/profile save myprofile` — save current settings as profile\n"
                "- `/profile delete myprofile` — remove a saved profile"
            )

        self.register(SlashCommand("workprofile", "Manage workspace configuration profiles", profile_handler))

        # ── Q57 Task 386: /replay — session replay ────────────────────────────

        async def replay_handler(arg: str = "", **_: Any) -> str:
            """/replay [session-id] [--dry-run] — replay user messages from a saved session."""
            from lidco.cli.session_store import SessionStore
            if registry._session_store is None:
                registry._session_store = SessionStore()
            store: "SessionStore" = registry._session_store

            parts = arg.strip().split()
            dry_run = "--dry-run" in parts
            session_id_parts = [p for p in parts if not p.startswith("--")]
            session_id = session_id_parts[0] if session_id_parts else None

            if not session_id:
                return (
                    "**Usage:** `/replay <session-id> [--dry-run]`\n\n"
                    "- `/replay abc123` — replay messages from session\n"
                    "- `/replay abc123 --dry-run` — preview without sending"
                )

            data = store.load(session_id)
            if data is None:
                return f"Session `{session_id}` not found."

            history = data.get("history", [])
            user_messages = [
                m.get("content", "") for m in history if m.get("role") == "user"
            ]
            if not user_messages:
                return f"Session `{session_id}` has no user messages to replay."

            if dry_run:
                lines = [f"**Dry run — {len(user_messages)} messages from `{session_id}`:**\n"]
                for i, msg in enumerate(user_messages, 1):
                    preview = str(msg)[:100].replace("\n", " ")
                    lines.append(f"  {i}. {preview}")
                return "\n".join(lines)

            # Confirm with user (non-blocking best effort)
            lines = [f"**Replaying {len(user_messages)} message(s) from `{session_id}`...**\n"]
            session = registry._session
            orch = getattr(session, "orchestrator", None)
            if orch is None:
                return "No active orchestrator to replay into."

            for i, msg in enumerate(user_messages, 1):
                preview = str(msg)[:60].replace("\n", " ")
                lines.append(f"  [{i}/{len(user_messages)}] Sending: {preview}…")
                try:
                    await orch.handle(str(msg))
                except Exception as exc:
                    lines.append(f"  ⚠ Error on message {i}: {exc}")
                    break

            lines.append("\nReplay complete.")
            return "\n".join(lines)

        self.register(SlashCommand("replay", "Replay user messages from a saved session", replay_handler))

        # ── Q57 Task 388: /repos — multi-repo support ─────────────────────────
        registry._extra_repos: "list[str]" = []

        async def repos_handler(arg: str = "", **_: Any) -> str:
            """/repos [add <path>|remove <path>|list] — manage additional repos."""
            import subprocess as _subprocess
            from pathlib import Path as _Path

            parts = arg.strip().split(maxsplit=1)
            sub = parts[0].lower() if parts else "list"
            rest = parts[1].strip() if len(parts) > 1 else ""

            if sub == "list" or not arg.strip():
                if not registry._extra_repos:
                    return (
                        "No extra repositories configured.\n"
                        "Usage: `/repos add <path>`"
                    )
                lines = ["**Extra repositories:**\n"]
                for repo in registry._extra_repos:
                    lines.append(f"  · `{repo}`")
                lines.append("\nOn each turn, git status + branch for these repos will be injected into context.")
                return "\n".join(lines)

            if sub == "add":
                if not rest:
                    return "Usage: `/repos add <path>`"
                p = _Path(rest).resolve()
                if not p.exists():
                    return f"Path not found: `{rest}`"
                if not p.is_dir():
                    return f"`{rest}` is not a directory."
                resolved = str(p)
                if resolved in registry._extra_repos:
                    return f"`{resolved}` is already in the repos list."
                # Verify it's a git repo
                try:
                    r = _subprocess.run(
                        ["git", "rev-parse", "--git-dir"],
                        cwd=resolved,
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if r.returncode != 0:
                        return f"`{resolved}` does not appear to be a git repository."
                except Exception:
                    pass  # If git check fails, still add it
                registry._extra_repos.append(resolved)
                return f"Added `{resolved}` to repos list."

            if sub == "remove":
                if not rest:
                    return "Usage: `/repos remove <path>`"
                p = _Path(rest).resolve()
                resolved = str(p)
                if resolved in registry._extra_repos:
                    registry._extra_repos.remove(resolved)
                    return f"Removed `{resolved}` from repos list."
                # Try fuzzy match
                if rest in registry._extra_repos:
                    registry._extra_repos.remove(rest)
                    return f"Removed `{rest}` from repos list."
                return f"`{rest}` not found in repos list."

            return (
                "**Usage:** `/repos [add <path>|remove <path>|list]`\n\n"
                "- `/repos add ../backend` — add a repo\n"
                "- `/repos remove ../backend` — remove a repo\n"
                "- `/repos list` — show configured repos"
            )

        self.register(SlashCommand("repos", "Manage multiple repositories", repos_handler))

        # ── Q42 — TDD Pipeline & Batch (Tasks 286–292) ───────────────────────

        # Task 287: /spec — generate a specification
        async def spec_handler(arg: str = "", **_: Any) -> str:
            """/spec <task> | list | load <name> — generate or view specifications."""
            session = registry._session
            parts = arg.strip().split(maxsplit=1)
            sub = parts[0].lower() if parts else ""
            rest = parts[1] if len(parts) > 1 else ""

            if sub == "list":
                from lidco.tdd.spec_writer import SpecWriter
                writer = SpecWriter(session)
                specs = writer.list_specs()
                if not specs:
                    return "No specs saved yet. Use `/spec <task>` to generate one."
                lines = ["**Saved specifications:**\n"]
                for s in specs:
                    lines.append(f"  · `{s['name']}` — {s['goal'][:60]}")
                return "\n".join(lines)

            if sub == "load":
                if not rest:
                    return "Usage: `/spec load <name>`"
                from lidco.tdd.spec_writer import SpecWriter
                writer = SpecWriter(session)
                spec = writer.load(rest)
                if spec is None:
                    return f"Spec `{rest}` not found."
                return f"**Spec: {spec.goal}**\n\n{spec.content[:2000]}"

            # Generate new spec
            task = arg.strip() if not sub else arg.strip()
            if not task:
                return (
                    "**Usage:** `/spec <task description>`\n\n"
                    "- `/spec add JWT authentication` — generate a spec\n"
                    "- `/spec list` — list saved specs\n"
                    "- `/spec load <name>` — view a saved spec"
                )
            from lidco.tdd.spec_writer import SpecWriter
            writer = SpecWriter(session)
            spec = await writer.generate(task)
            path = writer.save(spec)
            return f"**Specification generated** → saved to `{path}`\n\n{spec.content[:3000]}"

        self.register(SlashCommand("spec", "Generate a structured feature specification", spec_handler))

        # Task 286: /tdd — run TDD pipeline
        async def tdd_handler(arg: str = "", **_: Any) -> str:
            """/tdd <task> [--test <file>] [--impl <file>] [--cycles N] — run TDD pipeline."""
            import re as _re
            session = registry._session
            if not arg.strip():
                return (
                    "**Usage:** `/tdd <task> [--test <file>] [--impl <file>] [--cycles N]`\n\n"
                    "Runs the full TDD pipeline: spec → RED tests → GREEN implementation → review.\n"
                    "Example: `/tdd add binary search to utils.py`"
                )
            # Parse flags
            test_file = None
            impl_file = None
            max_cycles = 3
            task_text = arg

            m = _re.search(r"--test\s+(\S+)", arg)
            if m:
                test_file = m.group(1)
                task_text = task_text.replace(m.group(0), "").strip()

            m = _re.search(r"--impl\s+(\S+)", arg)
            if m:
                impl_file = m.group(1)
                task_text = task_text.replace(m.group(0), "").strip()

            m = _re.search(r"--cycles\s+(\d+)", arg)
            if m:
                max_cycles = int(m.group(1))
                task_text = task_text.replace(m.group(0), "").strip()

            from lidco.tdd.pipeline import TDDPipeline
            pipeline = TDDPipeline(
                session,
                test_file=test_file,
                impl_file=impl_file,
                max_cycles=max_cycles,
            )
            result = await pipeline.run(task_text)
            return result.summary()

        self.register(SlashCommand("tdd", "Run the TDD pipeline (spec→RED→GREEN→verify)", tdd_handler))

        # Task 288: /batch — parallel task decomposition
        async def batch_handler(arg: str = "", **_: Any) -> str:
            """/batch <task> [--n N] [--agent name] — decompose and run in parallel."""
            import re as _re
            session = registry._session
            if not arg.strip():
                return (
                    "**Usage:** `/batch <task> [--n N] [--agent name]`\n\n"
                    "Decomposes a large task into N independent units and runs them in parallel.\n"
                    "Example: `/batch add docstrings to all public functions in src/ --n 8`"
                )
            n = 5
            agent_name = None
            task_text = arg

            m = _re.search(r"--n\s+(\d+)", arg)
            if m:
                n = max(2, min(int(m.group(1)), 20))
                task_text = task_text.replace(m.group(0), "").strip()

            m = _re.search(r"--agent\s+(\S+)", arg)
            if m:
                agent_name = m.group(1)
                task_text = task_text.replace(m.group(0), "").strip()

            from lidco.tdd.batch import BatchProcessor
            processor = BatchProcessor(session, n_units=n)
            job = await processor.run(task_text, agent_name=agent_name)
            return job.summary()

        self.register(SlashCommand("batch", "Decompose and run tasks in parallel", batch_handler))

        # Task 289: /simplify — parallel code review
        async def simplify_handler(arg: str = "", **_: Any) -> str:
            """/simplify [file] — run 3 parallel reviewers and merge findings."""
            session = registry._session
            if not arg.strip():
                return (
                    "**Usage:** `/simplify <file_or_task>`\n\n"
                    "Runs 3 parallel reviewers and merges their findings.\n"
                    "Example: `/simplify src/auth.py`"
                )
            from lidco.tdd.batch import BatchProcessor
            target = arg.strip()
            # Three parallel review perspectives
            sub_tasks = [
                f"Review `{target}` for correctness and logic bugs",
                f"Review `{target}` for code quality, readability, and style",
                f"Review `{target}` for security vulnerabilities and edge cases",
            ]
            processor = BatchProcessor(session, max_concurrent=3, n_units=3)
            # Run all 3 reviewers in parallel using decomposed tasks directly
            import asyncio as _asyncio
            from lidco.tdd.batch import BatchJob, BatchUnit
            job = BatchJob(original_task=f"Review: {target}")
            for i, t in enumerate(sub_tasks, 1):
                job.units.append(BatchUnit(index=i, task=t))

            semaphore = _asyncio.Semaphore(3)
            async def _run_unit(unit: "BatchUnit") -> None:
                async with semaphore:
                    unit.status = "running"
                    try:
                        response = await session.orchestrator.handle(
                            unit.task, agent_name="reviewer"
                        )
                        unit.result = response.content if hasattr(response, "content") else str(response)
                        unit.status = "done"
                    except Exception as exc:
                        unit.status = "failed"
                        unit.error = str(exc)

            await _asyncio.gather(*[_run_unit(u) for u in job.units])

            lines = [f"**Parallel Review: {target}**\n"]
            labels = ["Correctness", "Code Quality", "Security"]
            for unit, label in zip(job.units, labels):
                if unit.status == "done":
                    lines.append(f"### {label}\n{unit.result[:600]}\n")
                else:
                    lines.append(f"### {label}\nFailed: {unit.error[:100]}\n")
            return "\n".join(lines)

        self.register(SlashCommand("simplify", "Run parallel code review and merge findings", simplify_handler))

        # Task 290: /best-of — best-of-N code generation
        async def bestof_handler(arg: str = "", **_: Any) -> str:
            """/best-of <N> <task> [--test <file>] [--impl <file>] — best-of-N generation."""
            import re as _re
            session = registry._session
            if not arg.strip():
                return (
                    "**Usage:** `/best-of <N> <task> [--test <file>] [--impl <file>]`\n\n"
                    "Generates N code variants and picks the best by test results.\n"
                    "Example: `/best-of 3 implement quicksort --test tests/test_sort.py`"
                )
            # Parse N
            m = _re.match(r"^(\d+)\s+", arg.strip())
            n = int(m.group(1)) if m else 3
            task_text = arg.strip()[len(m.group(0)):] if m else arg.strip()

            test_file = None
            impl_file = None
            tm = _re.search(r"--test\s+(\S+)", task_text)
            if tm:
                test_file = tm.group(1)
                task_text = task_text.replace(tm.group(0), "").strip()
            im = _re.search(r"--impl\s+(\S+)", task_text)
            if im:
                impl_file = im.group(1)
                task_text = task_text.replace(im.group(0), "").strip()

            from lidco.tdd.best_of_n import BestOfN
            selector = BestOfN(session, n=n)
            result = await selector.run(task_text, test_file=test_file, impl_file=impl_file)
            return result.summary()

        self.register(SlashCommand("best-of", "Best-of-N code generation via parallel attempts", bestof_handler))

        # Task 291: /tdd-mode — test-first enforcement
        registry._test_first_mode: str = "off"  # off | warn | block

        async def tddmode_handler(arg: str = "", **_: Any) -> str:
            """/tdd-mode [off|warn|block] — control test-first enforcement."""
            mode = arg.strip().lower()
            if mode not in ("", "off", "warn", "block"):
                return "Usage: `/tdd-mode [off|warn|block]`"

            if not mode:
                enforcer = getattr(registry, "_test_first_enforcer", None)
                current = registry._test_first_mode
                return (
                    f"**Test-first mode:** `{current}`\n\n"
                    "- `off` — no enforcement\n"
                    "- `warn` — warn when impl written before tests\n"
                    "- `block` — block impl writes until tests exist"
                )

            registry._test_first_mode = mode
            enforcer = getattr(registry, "_test_first_enforcer", None)
            if enforcer is not None:
                if mode == "off":
                    enforcer.set_enabled(False)
                else:
                    enforcer.set_enabled(True)
                    enforcer.set_mode(mode)
            return f"Test-first enforcement set to `{mode}`."

        self.register(SlashCommand("tdd-mode", "Control test-first write enforcement", tddmode_handler))

        # ── Q43 — Skills & Plugin System (Tasks 293–299) ─────────────────────

        # Lazy-loaded skill registry (Tasks 293, 294, 297)
        registry._skill_registry: Any = None

        def _get_skill_registry() -> Any:
            from lidco.skills.registry import SkillRegistry
            if registry._skill_registry is None:
                reg = SkillRegistry()
                reg.load()
                registry._skill_registry = reg
            return registry._skill_registry

        # Task 298: /skills — list/describe/run/edit/reload skills
        async def skills_handler(arg: str = "", **_: Any) -> str:
            """/skills [list|describe <name>|run <name> [args]|reload|validate] — manage skills."""
            session = registry._session
            skill_reg = _get_skill_registry()
            parts = arg.strip().split(maxsplit=2)
            sub = parts[0].lower() if parts else "list"
            rest = parts[1] if len(parts) > 1 else ""
            extra = parts[2] if len(parts) > 2 else ""

            if sub in ("list", ""):
                skills = skill_reg.list_skills()
                if not skills:
                    return (
                        "No skills found.\n\n"
                        "Create a skill file in `.lidco/skills/` or `~/.lidco/skills/`:\n"
                        "```yaml\n---\nname: review\ndescription: Review code\n---\nReview: {args}\n```"
                    )
                lines = [f"**Skills ({len(skills)} loaded):**\n"]
                for s in skills:
                    ver = f" v{s.version}" if s.version != "1.0" else ""
                    req = f" [requires: {', '.join(s.requires)}]" if s.requires else ""
                    lines.append(f"  · `/{s.name}`{ver} — {s.description}{req}")
                lines.append("\nUse `/skills describe <name>` for details, `/skills run <name> [args]` to execute.")
                return "\n".join(lines)

            if sub == "describe":
                if not rest:
                    return "Usage: `/skills describe <name>`"
                skill = skill_reg.get(rest)
                if skill is None:
                    return f"Skill `{rest}` not found. Use `/skills list` to see available skills."
                lines = [
                    f"**Skill: {skill.name}** (v{skill.version})",
                    f"*{skill.description}*" if skill.description else "",
                    f"**File:** `{skill.path}`",
                ]
                if skill.requires:
                    lines.append(f"**Requires:** {', '.join(skill.requires)}")
                if skill.context:
                    lines.append(f"**Context:** `{skill.context}`")
                if skill.scripts:
                    for hook, cmd in skill.scripts.items():
                        lines.append(f"**Script ({hook}):** `{cmd}`")
                lines.append(f"\n**Prompt template:**\n```\n{skill.prompt[:800]}\n```")
                return "\n".join(l for l in lines if l)

            if sub == "run":
                if not rest:
                    return "Usage: `/skills run <name> [args]`"
                # Support pipe syntax: /skills run skill1 | skill2
                full_expr = f"{rest} {extra}".strip() if extra else rest
                if "|" in full_expr:
                    from lidco.skills.chain import SkillChain
                    chain = SkillChain(skill_reg, session)
                    result = await chain.run(full_expr)
                    return result.summary()

                skill = skill_reg.get(rest)
                if skill is None:
                    return f"Skill `{rest}` not found."
                missing = skill.check_requirements()
                if missing:
                    return f"⚠️ Missing required tools: {', '.join(missing)}"
                skill.run_script("pre")
                prompt = skill.render(extra)
                try:
                    context = ""
                    if skill.context:
                        from pathlib import Path as _P
                        cp = _P(skill.context)
                        if cp.is_file():
                            context = cp.read_text(encoding="utf-8", errors="replace")[:3000]
                    response = await session.orchestrator.handle(prompt, context=context or None)
                    output = response.content if hasattr(response, "content") else str(response)
                    skill.run_script("post")
                    return output
                except Exception as exc:
                    return f"Skill `{rest}` failed: {exc}"

            if sub == "reload":
                skill_reg.reload()
                n = len(skill_reg.list_skills())
                return f"Skills reloaded — {n} skill(s) available."

            if sub == "validate":
                from lidco.skills.validator import SkillValidator
                validator = SkillValidator()
                skills = skill_reg.list_skills()
                if not skills:
                    return "No skills to validate."
                lines = [f"**Skill validation ({len(skills)} skills):**\n"]
                all_ok = True
                for s in skills:
                    result = validator.validate(s)
                    if result.valid:
                        lines.append(f"  ✅ `{s.name}`")
                    else:
                        all_ok = False
                        lines.append(f"  ❌ `{s.name}`:")
                        for issue in result.issues:
                            lines.append(f"     · {issue}")
                if all_ok:
                    lines.append("\nAll skills are valid.")
                return "\n".join(lines)

            return (
                "**Usage:** `/skills [list|describe <name>|run <name> [args]|reload|validate]`\n\n"
                "- `/skills` — list all skills\n"
                "- `/skills describe <name>` — show skill details\n"
                "- `/skills run <name> [args]` — execute a skill\n"
                "- `/skills run skill1 | skill2` — chain skills\n"
                "- `/skills reload` — rescan skill directories\n"
                "- `/skills validate` — check all skills for issues"
            )

        self.register(SlashCommand("skills", "List, run, and manage reusable skills", skills_handler))

        # ── Q56 Task 375: /conflict — AI conflict resolver ─────────────────────

        async def conflict_handler(arg: str = "", **_: Any) -> str:
            """/conflict [file] — resolve git merge conflicts interactively."""
            import asyncio as _asyncio
            import subprocess as _subprocess

            from lidco.tools.conflict_resolver import (
                ConflictBlock as _CB,
                find_conflicted_files,
                parse_conflict_blocks,
                apply_resolution,
            )

            target_file = arg.strip()

            # Find conflicted files
            if target_file:
                candidates = [target_file]
            else:
                candidates = find_conflicted_files()

            if not candidates:
                return "No conflicted files found. Run `git merge` or `git rebase` first."

            lines: list[str] = []
            for fpath in candidates:
                blocks = parse_conflict_blocks(fpath)
                if not blocks:
                    lines.append(f"No conflict markers in `{fpath}`.")
                    continue

                lines.append(f"## Conflicts in `{fpath}` ({len(blocks)} block{'s' if len(blocks) != 1 else ''})\n")
                resolutions: list[str] = []

                for idx, block in enumerate(blocks, 1):
                    lines.append(f"### Block {idx} (line {block.start_line})")
                    lines.append("**Ours:**")
                    lines.append(f"```\n{block.ours}\n```")
                    lines.append("**Theirs:**")
                    lines.append(f"```\n{block.theirs}\n```")
                    lines.append("")

                    # Auto-resolution: provide structured info for AI analysis
                    if registry._session:
                        try:
                            from lidco.llm.base import Message as _LLMMsg
                            prompt = (
                                "You are resolving a git merge conflict. Choose the best resolution.\n\n"
                                f"File: {block.file}\n"
                            )
                            if block.context_before:
                                prompt += f"Context before:\n```\n{block.context_before}\n```\n\n"
                            prompt += (
                                f"<<<<<<< ours\n{block.ours}\n=======\n{block.theirs}\n>>>>>>> theirs\n\n"
                            )
                            if block.context_after:
                                prompt += f"Context after:\n```\n{block.context_after}\n```\n\n"
                            prompt += (
                                "Output ONLY the resolved code that should replace the conflict block. "
                                "No explanation, no markers."
                            )
                            resp = await registry._session.llm.complete(
                                [_LLMMsg(role="user", content=prompt)],
                                temperature=0.1,
                                max_tokens=512,
                            )
                            ai_resolution = (resp.content or "").strip()
                            resolutions.append(ai_resolution)
                            lines.append(f"**AI suggestion:**")
                            lines.append(f"```\n{ai_resolution}\n```")
                        except Exception as exc:
                            resolutions.append(block.ours)
                            lines.append(f"*(AI unavailable: {exc} — defaulting to ours)*")
                    else:
                        resolutions.append(block.ours)

                lines.append("")

            return "\n".join(lines)

        self.register(SlashCommand("conflict", "Resolve git merge conflicts with AI assistance", conflict_handler))

        # ── Q56 Task 376: /bisect — git bisect integration ─────────────────────

        async def bisect_handler(arg: str = "", **_: Any) -> str:
            """/bisect <start <test>|run|stop> — git bisect integration."""
            import asyncio as _asyncio
            import subprocess as _subprocess

            parts = arg.strip().split(None, 1)
            sub = parts[0].lower() if parts else ""
            rest = parts[1] if len(parts) > 1 else ""

            def _git(*cmd: str, timeout: int = 30) -> tuple[str, str, int]:
                try:
                    r = _subprocess.run(
                        ["git"] + list(cmd),
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=timeout,
                    )
                    return r.stdout.strip(), r.stderr.strip(), r.returncode
                except FileNotFoundError:
                    return "", "git not found", -1
                except _subprocess.TimeoutExpired:
                    return "", "timeout", -2

            if sub == "stop":
                out, err, rc = _git("bisect", "reset")
                if rc != 0:
                    return f"bisect reset failed: {err}"
                return f"Git bisect stopped.\n```\n{out}\n```"

            if sub == "start":
                if not rest.strip():
                    return "Usage: `/bisect start <test-expression>`\n\nExample: `/bisect start pytest tests/test_foo.py -k test_bar`"

                test_expr = rest.strip()
                # Start bisect
                out1, err1, rc1 = _git("bisect", "start")
                if rc1 != 0:
                    return f"Failed to start bisect: {err1}"

                # Mark HEAD as bad
                out2, err2, rc2 = _git("bisect", "bad")
                if rc2 != 0:
                    return f"Failed to mark HEAD bad: {err2}"

                # Find last 10 commits to pick a "good" baseline
                log_out, _, _ = _git("log", "--oneline", "-20")
                commit_lines = [ln for ln in log_out.splitlines() if ln.strip()]
                commits_list = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(commit_lines))

                result_lines = [
                    "## Git Bisect Started",
                    "",
                    f"Test expression: `{test_expr}`",
                    "",
                    "HEAD marked as **bad**. Recent commits:",
                    f"```\n{commits_list}\n```",
                    "",
                    "Mark the last known good commit with:",
                    f"`git bisect good <hash>`",
                    "",
                    "Then run `/bisect run` to automate the search.",
                ]
                return "\n".join(result_lines)

            if sub == "run":
                # Run a bisect iteration: test current commit
                test_expr = rest.strip()
                if not test_expr:
                    return "Usage: `/bisect run <test-expression>`"

                try:
                    proc = _subprocess.run(
                        test_expr.split(),
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=60,
                    )
                    test_passed = proc.returncode == 0
                except (FileNotFoundError, _subprocess.TimeoutExpired) as e:
                    return f"Failed to run test: {e}"

                mark = "good" if test_passed else "bad"
                bisect_out, bisect_err, bisect_rc = _git("bisect", mark)
                full_out = bisect_out or bisect_err

                result_lines = [
                    f"## Bisect Step: marked **{mark}**",
                    "",
                    f"Test `{test_expr}` {'passed' if test_passed else 'failed'}.",
                    "",
                    f"```\n{full_out}\n```",
                ]

                # Check if bisect found the culprit
                if "is the first bad commit" in full_out or "bisect found" in full_out.lower():
                    # Extract commit hash
                    culprit_hash = ""
                    for ln in full_out.splitlines():
                        if ln and not ln.startswith("[") and len(ln.split()) >= 1:
                            culprit_hash = ln.split()[0]
                            break

                    result_lines.append("")
                    result_lines.append("**Culprit commit found!**")

                    if culprit_hash and registry._session:
                        try:
                            show_out, _, _ = _git("show", "--stat", culprit_hash, timeout=10)
                            from lidco.llm.base import Message as _LLMMsg
                            explain_resp = await registry._session.llm.complete(
                                [_LLMMsg(role="user", content=(
                                    f"Explain this git commit and why it might have introduced a bug:\n\n"
                                    f"```\n{show_out[:2000]}\n```\n\n"
                                    "Be concise (2-3 sentences)."
                                ))],
                                temperature=0.2,
                                max_tokens=150,
                            )
                            result_lines.append("")
                            result_lines.append(f"**AI explanation:** {(explain_resp.content or '').strip()}")
                        except Exception:
                            pass

                return "\n".join(result_lines)

            return (
                "**Usage:** `/bisect <subcommand>`\n\n"
                "- `/bisect start <test-expr>` — start bisect, mark HEAD as bad\n"
                "- `/bisect run <test-expr>` — run test on current commit, auto-mark\n"
                "- `/bisect stop` — abort bisect session\n\n"
                "**Example:** `/bisect start pytest tests/ -k test_login`"
            )

        self.register(SlashCommand("bisect", "Git bisect integration for finding regressions", bisect_handler))

        # ── Q56 Task 377: /branch, /checkout, /stash ──────────────────────────

        async def branch_handler(arg: str = "", **_: Any) -> str:
            """/branch [list|create <name>|delete <name>|rename <old> <new>]."""
            import subprocess as _subprocess

            def _git(*cmd: str) -> tuple[str, str, int]:
                try:
                    r = _subprocess.run(
                        ["git"] + list(cmd),
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=30,
                    )
                    return r.stdout.strip(), r.stderr.strip(), r.returncode
                except FileNotFoundError:
                    return "", "git not found", -1
                except _subprocess.TimeoutExpired:
                    return "", "timeout", -2

            parts = arg.strip().split()
            sub = parts[0].lower() if parts else "list"

            if sub == "list" or sub == "" or not parts:
                out, err, rc = _git("branch", "-a", "--color=never")
                if rc != 0:
                    return f"Error listing branches: {err}"
                if not out:
                    return "No branches found."
                branch_lines = []
                for ln in out.splitlines():
                    marker = "**" if ln.startswith("*") else ""
                    branch_lines.append(f"  {marker}{ln.strip()}{marker}")
                return "## Branches\n\n" + "\n".join(branch_lines)

            if sub == "create" and len(parts) >= 2:
                name = parts[1]
                out, err, rc = _git("branch", name)
                if rc != 0:
                    return f"Failed to create branch `{name}`: {err}"
                return f"Branch `{name}` created."

            if sub == "delete" and len(parts) >= 2:
                name = parts[1]
                out, err, rc = _git("branch", "-d", name)
                if rc != 0:
                    # Try force delete
                    out2, err2, rc2 = _git("branch", "-D", name)
                    if rc2 != 0:
                        return f"Failed to delete branch `{name}`: {err}"
                    return f"Branch `{name}` force-deleted."
                return f"Branch `{name}` deleted."

            if sub == "rename" and len(parts) >= 3:
                old, new = parts[1], parts[2]
                out, err, rc = _git("branch", "-m", old, new)
                if rc != 0:
                    return f"Failed to rename `{old}` to `{new}`: {err}"
                return f"Branch renamed: `{old}` → `{new}`."

            return (
                "**Usage:** `/branch [list|create <name>|delete <name>|rename <old> <new>]`\n\n"
                "- `/branch` — list all branches\n"
                "- `/branch create feature/my-work` — create a new branch\n"
                "- `/branch delete old-branch` — delete a branch\n"
                "- `/branch rename old-name new-name` — rename a branch"
            )

        self.register(SlashCommand("branch", "Manage git branches", branch_handler))

        async def checkout_handler(arg: str = "", **_: Any) -> str:
            """/checkout <branch-or-file> — switch branches or restore files."""
            import subprocess as _subprocess

            target = arg.strip()
            if not target:
                return "**Usage:** `/checkout <branch-or-file>`"

            try:
                r = _subprocess.run(
                    ["git", "checkout", target],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                )
                if r.returncode != 0:
                    return f"Checkout failed:\n```\n{r.stderr.strip()}\n```"
                out = (r.stdout + r.stderr).strip()
                return f"Checked out `{target}`." + (f"\n```\n{out}\n```" if out else "")
            except FileNotFoundError:
                return "Git not found."
            except _subprocess.TimeoutExpired:
                return "Checkout timed out."

        self.register(SlashCommand("checkout", "Checkout a branch or restore a file", checkout_handler))

        async def stash_handler(arg: str = "", **_: Any) -> str:
            """/stash [list|push [message]|pop [index]|drop [index]]."""
            import subprocess as _subprocess

            def _git(*cmd: str) -> tuple[str, str, int]:
                try:
                    r = _subprocess.run(
                        ["git"] + list(cmd),
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=30,
                    )
                    return r.stdout.strip(), r.stderr.strip(), r.returncode
                except FileNotFoundError:
                    return "", "git not found", -1
                except _subprocess.TimeoutExpired:
                    return "", "timeout", -2

            parts = arg.strip().split(None, 1)
            sub = parts[0].lower() if parts else "list"
            rest = parts[1] if len(parts) > 1 else ""

            if sub == "list" or not parts:
                out, err, rc = _git("stash", "list")
                if rc != 0:
                    return f"Error: {err}"
                if not out:
                    return "No stashes found."
                return "## Stash List\n\n```\n" + out + "\n```"

            if sub == "push":
                cmd_args = ["stash", "push"]
                if rest.strip():
                    cmd_args += ["-m", rest.strip()]
                out, err, rc = _git(*cmd_args)
                if rc != 0:
                    return f"Stash push failed: {err}"
                return f"Stashed changes." + (f"\n```\n{out}\n```" if out else "")

            if sub == "pop":
                cmd_args = ["stash", "pop"]
                if rest.strip():
                    cmd_args += [f"stash@{{{rest.strip()}}}"]
                out, err, rc = _git(*cmd_args)
                if rc != 0:
                    return f"Stash pop failed: {err}"
                return f"Popped stash." + (f"\n```\n{out}\n```" if out else "")

            if sub == "drop":
                cmd_args = ["stash", "drop"]
                if rest.strip():
                    cmd_args += [f"stash@{{{rest.strip()}}}"]
                out, err, rc = _git(*cmd_args)
                if rc != 0:
                    return f"Stash drop failed: {err}"
                return f"Dropped stash." + (f"\n```\n{out}\n```" if out else "")

            return (
                "**Usage:** `/stash [list|push [message]|pop [index]|drop [index]]`\n\n"
                "- `/stash` — list stashes\n"
                "- `/stash push Work in progress` — stash with message\n"
                "- `/stash pop` — apply latest stash\n"
                "- `/stash pop 1` — apply stash@{1}\n"
                "- `/stash drop 0` — drop stash@{0}"
            )

        self.register(SlashCommand("stash", "Manage git stashes", stash_handler))

        # ── Q56 Task 378: /pr create — AI-generated PR creation ───────────────
        # NOTE: Extends existing /pr (which handles load/context). We register
        # a new 'pr-create' command AND patch pr_handler to support 'create'.

        async def pr_create_handler(arg: str = "", **_: Any) -> str:
            """/pr-create [--draft] [--base <branch>] — create a PR with AI-generated title/body."""
            import subprocess as _subprocess

            # Parse flags
            draft = False
            base_branch = ""
            tokens = arg.strip().split()
            i = 0
            while i < len(tokens):
                if tokens[i] == "--draft":
                    draft = True
                    i += 1
                elif tokens[i] == "--base" and i + 1 < len(tokens):
                    base_branch = tokens[i + 1]
                    i += 2
                else:
                    i += 1

            def _run(*cmd: str, timeout: int = 30) -> tuple[str, str, int]:
                try:
                    r = _subprocess.run(
                        list(cmd),
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=timeout,
                    )
                    return r.stdout.strip(), r.stderr.strip(), r.returncode
                except FileNotFoundError:
                    return "", f"{cmd[0]} not found", -1
                except _subprocess.TimeoutExpired:
                    return "", "timeout", -2

            # Gather git context
            log_out, _, _ = _run("git", "log", "origin/HEAD..HEAD", "--oneline", timeout=15)
            if not log_out:
                log_out, _, _ = _run("git", "log", "-10", "--oneline", timeout=15)

            stat_out, _, _ = _run("git", "diff", "--stat", "origin/HEAD..HEAD", timeout=15)
            if not stat_out:
                stat_out, _, _ = _run("git", "diff", "--stat", "HEAD~1..HEAD", timeout=15)

            current_branch, _, _ = _run("git", "rev-parse", "--abbrev-ref", "HEAD")

            if not registry._session:
                return "Session not initialized. Cannot generate PR title/body."

            try:
                from lidco.llm.base import Message as _LLMMsg
                prompt = (
                    "Generate a GitHub pull request title and body for these changes.\n\n"
                    f"Branch: {current_branch}\n\n"
                    f"Commits:\n```\n{log_out[:1500]}\n```\n\n"
                    f"Diff stat:\n```\n{stat_out[:800]}\n```\n\n"
                    "Format your response exactly as:\n"
                    "TITLE: <one-line title under 70 chars>\n"
                    "BODY:\n<markdown body with Summary section and bullet points>\n"
                )
                resp = await registry._session.llm.complete(
                    [_LLMMsg(role="user", content=prompt)],
                    temperature=0.2,
                    max_tokens=500,
                )
                content = (resp.content or "").strip()
            except Exception as e:
                return f"Failed to generate PR content: {e}"

            # Parse generated title/body
            title = ""
            body = ""
            if "TITLE:" in content:
                lines_content = content.splitlines()
                for i2, ln in enumerate(lines_content):
                    if ln.startswith("TITLE:"):
                        title = ln[6:].strip()
                    elif ln.startswith("BODY:"):
                        body = "\n".join(lines_content[i2 + 1:]).strip()
                        break
            else:
                lines_content = content.splitlines()
                title = lines_content[0].strip() if lines_content else "Update"
                body = "\n".join(lines_content[1:]).strip()

            if not title:
                title = f"Update from {current_branch}"

            # Build gh command
            gh_cmd = ["gh", "pr", "create", "--title", title, "--body", body]
            if draft:
                gh_cmd.append("--draft")
            if base_branch:
                gh_cmd += ["--base", base_branch]

            preview_lines = [
                "## PR Preview",
                "",
                f"**Title:** {title}",
                "",
                f"**Body:**\n{body[:600]}{'...' if len(body) > 600 else ''}",
                "",
                f"**Command:** `{' '.join(gh_cmd[:6])} ...`",
                "",
                "_Run `gh pr create` manually or confirm with this command._",
            ]

            # Try to actually create
            out, err, rc = _run(*gh_cmd, timeout=30)
            if rc == 0:
                preview_lines.append("")
                preview_lines.append(f"PR created: {out}")
            else:
                preview_lines.append("")
                preview_lines.append(f"**Note:** `gh pr create` returned error: {err or out}")
                preview_lines.append("_You may need to push your branch first: `git push -u origin HEAD`_")

            return "\n".join(preview_lines)

        self.register(SlashCommand("pr-create", "Create a PR with AI-generated title and body", pr_create_handler))

        # ── Q56 Task 379: /pr-review <number> ─────────────────────────────────

        async def pr_review_handler(arg: str = "", **_: Any) -> str:
            """/pr-review <number> — AI-powered PR review with security+code analysis."""
            import subprocess as _subprocess

            pr_number = arg.strip()
            if not pr_number:
                return "**Usage:** `/pr-review <number>`\n\nExample: `/pr-review 123`"

            def _run(*cmd: str, timeout: int = 30) -> tuple[str, str, int]:
                try:
                    r = _subprocess.run(
                        list(cmd),
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=timeout,
                    )
                    return r.stdout.strip(), r.stderr.strip(), r.returncode
                except FileNotFoundError:
                    return "", f"{cmd[0]} not found", -1
                except _subprocess.TimeoutExpired:
                    return "", "timeout", -2

            diff_out, diff_err, diff_rc = _run("gh", "pr", "diff", pr_number, timeout=30)
            if diff_rc != 0:
                return f"Failed to fetch PR #{pr_number} diff: {diff_err or diff_out}"

            if not diff_out:
                return f"PR #{pr_number} has no diff or is empty."

            if not registry._session:
                return "Session not initialized."

            # Truncate large diffs
            diff_excerpt = diff_out[:6000]
            if len(diff_out) > 6000:
                diff_excerpt += f"\n... ({len(diff_out) - 6000} chars truncated)"

            try:
                from lidco.llm.base import Message as _LLMMsg
                prompt = (
                    f"Review this GitHub PR diff (PR #{pr_number}) as both a security expert "
                    "and a senior engineer.\n\n"
                    "Provide:\n"
                    "1. **Security issues** (if any) — list as inline comments with file:line\n"
                    "2. **Code quality issues** — style, logic, complexity\n"
                    "3. **Suggestions** — improvements, missing tests, etc.\n"
                    "4. **Overall verdict** — APPROVE / REQUEST_CHANGES / COMMENT\n\n"
                    f"```diff\n{diff_excerpt}\n```"
                )
                resp = await registry._session.llm.complete(
                    [_LLMMsg(role="user", content=prompt)],
                    temperature=0.2,
                    max_tokens=800,
                )
                review_content = (resp.content or "").strip()
            except Exception as e:
                return f"Failed to generate review: {e}"

            return f"## PR #{pr_number} Review\n\n{review_content}"

        self.register(SlashCommand("pr-review", "AI-powered review of a GitHub PR", pr_review_handler))

        # ── Q56 Task 381: enhance /commit with template support ───────────────
        # We replace the commit_handler registered earlier by re-registering
        # a new one that loads .lidco/commit-template.md if present.

        async def commit_with_template_handler(arg: str = "", **_: Any) -> str:
            """Enhanced /commit — generates commit message, optionally using .lidco/commit-template.md."""
            import asyncio as _asyncio
            import subprocess as _subprocess
            from pathlib import Path as _Path

            if not registry._session:
                return "Session not initialized."

            def _get_diff() -> tuple[str, str]:
                try:
                    r = _subprocess.run(
                        ["git", "diff", "--cached"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                    )
                    if r.stdout.strip():
                        return r.stdout.strip(), "staged"
                    r = _subprocess.run(
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

            def _load_template() -> str:
                """Load .lidco/commit-template.md if it exists."""
                for candidate in [
                    _Path(".lidco") / "commit-template.md",
                    _Path(".lidco") / "commit-template.txt",
                ]:
                    if candidate.exists():
                        try:
                            return candidate.read_text(encoding="utf-8", errors="replace").strip()
                        except OSError:
                            pass
                return ""

            loop = _asyncio.get_event_loop()
            diff, source = await loop.run_in_executor(None, _get_diff)

            if source.startswith("error:"):
                return f"Git error: {source[6:]}"
            if not diff:
                return "No changes found. Stage files with `git add` first."

            if arg.strip():
                commit_msg = arg.strip()
            else:
                diff_excerpt = diff[:4000]
                template = await loop.run_in_executor(None, _load_template)

                template_section = ""
                if template:
                    template_section = (
                        f"\n\nCommit message template to follow:\n```\n{template}\n```\n"
                        "Use the template format above for the commit message."
                    )

                from lidco.llm.base import Message as _LLMMsg2
                try:
                    resp = await registry._session.llm.complete(
                        [_LLMMsg2(role="user", content=(
                            "Write a git commit message for these changes.\n"
                            "Rules: one line, max 72 chars, format '<type>: <description>'\n"
                            "Types: feat, fix, refactor, docs, test, chore, perf\n"
                            f"{template_section}\n"
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
                from rich.console import Console as _RC2
                from rich.panel import Panel as _Panel2
                from rich.prompt import Prompt as _Prompt2

                c = _RC2()
                c.print()
                c.print(_Panel2(
                    f"[bold cyan]{msg}[/bold cyan]\n\n[dim]Changes: {diff_source}[/dim]",
                    title="Proposed Commit",
                    border_style="cyan",
                ))
                answer = _Prompt2.ask(
                    "Commit? [[green]y[/green]/[yellow]e[/yellow]dit/[red]n[/red]]",
                    default="y",
                )
                if answer.lower() in ("n", "no", "q", "cancel"):
                    return "__CANCEL__"
                if answer.lower() in ("e", "edit"):
                    msg = _Prompt2.ask("New message", default=msg)

                staged_check = _subprocess.run(
                    ["git", "diff", "--cached", "--quiet"],
                    capture_output=True, timeout=5,
                )
                if staged_check.returncode == 0:
                    add_result = _subprocess.run(
                        ["git", "add", "-u"], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=10,
                    )
                    if add_result.returncode != 0:
                        return f"__ERROR__:Failed to stage changes: {add_result.stderr.strip()}"

                result = _subprocess.run(
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

        # Override the existing /commit with template-aware version
        self.register(SlashCommand("commit", "Generate a commit message and commit (supports .lidco/commit-template.md)", commit_with_template_handler))

        # ── Q58 Task 389: /compare ────────────────────────────────────────────────
        async def compare_handler(arg: str = "", **_: Any) -> str:
            """Compare two files (diff) or run a task on multiple agents.

            File comparison (Task 198):
              /compare <file1> <file2>

            Agent comparison (Task 389):
              /compare <task>
              /compare --agents coder,architect <task>
            """
            import difflib as _difflib

            _PLANNING_AGENTS_LIST = ["coder", "architect", "tester", "refactor", "debugger"]
            agent_names: list[str] = []
            task_text = (arg or "").strip()

            # ── File comparison mode: detect two path-like arguments ──────────
            # Only when NOT using --agents flag and NOT starting with a verb-like word
            if task_text and not task_text.startswith("--agents "):
                parts_cmp = task_text.split(None, 1)
                if len(parts_cmp) == 2:
                    p1_str, p2_str = parts_cmp[0], parts_cmp[1].strip()
                    # Heuristic: if both look like file paths (have extension or abs path)
                    _path_like = lambda s: "/" in s or "\\" in s or "." in s.split("/")[-1]
                    if _path_like(p1_str) and not p2_str.startswith("--") and not any(
                        c in p1_str for c in (" ",)
                    ):
                        p1 = Path(p1_str)
                        p2 = Path(p2_str)
                        # If first token looks like a file path, treat as file diff
                        if p1.suffix or p1.is_absolute() or p2.suffix or p2.is_absolute():
                            # File diff mode
                            if not p1.exists():
                                return f"File not found: `{p1_str}`"
                            if p1.is_dir():
                                return f"`{p1_str}` is a directory, not a file."
                            if not p2.exists():
                                return f"File not found: `{p2_str}`"
                            if p2.is_dir():
                                return f"`{p2_str}` is a directory, not a file."
                            text1 = p1.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
                            text2 = p2.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
                            diff = list(_difflib.unified_diff(text1, text2, fromfile=p1_str, tofile=p2_str))
                            size1 = p1.stat().st_size
                            size2 = p2.stat().st_size
                            added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
                            removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
                            if not diff:
                                return (
                                    f"**{p1_str}** and **{p2_str}** are identical.\n\n"
                                    f"Size: {size1} bytes"
                                )
                            diff_text = "".join(diff)
                            _MAX_DIFF_LINES = 200
                            diff_lines = diff_text.splitlines()
                            hidden = 0
                            if len(diff_lines) > _MAX_DIFF_LINES:
                                hidden = len(diff_lines) - _MAX_DIFF_LINES
                                diff_text = "\n".join(diff_lines[:_MAX_DIFF_LINES])
                            header = (
                                f"**{p1_str}** ({size1} bytes) → **{p2_str}** ({size2} bytes)\n"
                                f"+{added} added / -{removed} removed\n\n"
                            )
                            result_str = header + f"```diff\n{diff_text}\n```"
                            if hidden:
                                result_str += f"\n\n_{hidden} lines hidden_"
                            return result_str

            # ── Agent comparison mode ─────────────────────────────────────────
            # Parse --agents flag
            if task_text.startswith("--agents "):
                rest = task_text[len("--agents "):].strip()
                if " " in rest:
                    agents_str, task_text = rest.split(" ", 1)
                    task_text = task_text.strip()
                else:
                    agents_str, task_text = rest, ""
                agent_names = [a.strip() for a in agents_str.split(",") if a.strip()]

            if not task_text:
                return (
                    "Usage:\n"
                    "  `/compare <file1> <file2>` — diff two files\n"
                    "  `/compare <task>` — run task on multiple agents\n"
                    "  `/compare --agents coder,tester <task>` — specify agents"
                )

            if len(task_text.split()) == 1 and not agent_names:
                # Single token that didn't match two files — show better error
                return (
                    f"Need two file paths or a task description.\n\n"
                    "  `/compare <file1> <file2>` — diff two files\n"
                    "  `/compare <task words>` — run agents on a task"
                )

            if not registry._session:
                return "Session not initialized."

            if not agent_names:
                # Use top 3 planning agents that are registered
                reg = registry._session.agent_registry
                available = {a.name for a in reg.list_agents()} if reg else set()
                agent_names = [
                    n for n in _PLANNING_AGENTS_LIST if n in available
                ][:3]
                if not agent_names:
                    agent_names = _PLANNING_AGENTS_LIST[:3]

            from lidco.agents.comparison import AgentComparator
            comparator = AgentComparator()
            result = await comparator.run(task_text, agent_names, registry._session)

            if not result.results:
                return "No agents available for comparison."

            lines: list[str] = [f"## Comparison: `{task_text[:60]}`\n"]
            for i, ar in enumerate(result.results):
                idx = i + 1
                if ar.success:
                    preview = ar.response[:600]
                    if len(ar.response) > 600:
                        preview += "\n...(truncated)"
                    lines.append(
                        f"### [{idx}] {ar.agent_name} "
                        f"({ar.elapsed:.1f}s{', ' + str(ar.tokens) + ' tok' if ar.tokens else ''})"
                    )
                    lines.append(preview)
                else:
                    lines.append(f"### [{idx}] {ar.agent_name} — FAILED: {ar.error}")
                lines.append("")

            lines.append("---")
            lines.append(
                "Select the best result by replying with its number, "
                "or continue with your next message."
            )
            return "\n".join(lines)

        self.register(SlashCommand("compare", "Compare files (diff) or run task on multiple agents", compare_handler))

        # ── Q58 Task 390 & 393: /pipeline ─────────────────────────────────────
        # Stores paused pipeline state for /pipeline resume
        registry._pipeline_state: "dict[str, Any]" = {}  # type: ignore[assignment]

        async def pipeline_handler(arg: str = "", **_: Any) -> str:
            """Load and run a declarative YAML agent pipeline.

            /pipeline <yaml-file>         — load from file and run
            /pipeline resume              — resume paused pipeline
            /pipeline inline: <yaml>      — run inline YAML (newlines as \\n)
            """
            if not registry._session:
                return "Session not initialized."

            arg = (arg or "").strip()

            # /pipeline resume
            if arg == "resume":
                state = getattr(registry, "_pipeline_state", {})
                if not state:
                    return "No paused pipeline to resume."
                yaml_str = state.get("yaml_str", "")
                task_text = state.get("task", "")
                if not yaml_str or not task_text:
                    return "Paused pipeline state is incomplete."
                registry._pipeline_state = {}  # type: ignore[assignment]
                # Re-run from scratch (simplest safe approach)
                arg = ""  # fall through to re-run logic below
                from lidco.agents.pipeline import AgentPipeline
                pipeline_obj = AgentPipeline()
                try:
                    pipeline_obj.load(yaml_str)
                except ValueError as exc:
                    return f"Pipeline YAML error: {exc}"
                result = await pipeline_obj.run(task_text, registry._session)
                return _format_pipeline_result(result)

            if not arg:
                return (
                    "Usage:\n"
                    "  `/pipeline <yaml-file>` — run pipeline from YAML file\n"
                    "  `/pipeline resume` — resume paused pipeline\n"
                    "  `/pipeline inline: <yaml>` — run inline YAML"
                )

            from lidco.agents.pipeline import AgentPipeline

            # Parse task and yaml source
            yaml_str = ""
            task_text = ""

            if arg.startswith("inline:"):
                # /pipeline inline: steps:\n  - name: ...
                rest = arg[len("inline:"):].strip()
                # treat first line as task if it doesn't look like yaml
                lines_split = rest.split("\\n")
                yaml_str = "\n".join(lines_split)
                task_text = "Execute pipeline"
            else:
                # Treat arg as: [task ]<yaml-file>
                # If arg ends in .yaml or .yml assume it's a file
                parts = arg.split(None, 1)
                if len(parts) == 2 and (parts[1].endswith(".yaml") or parts[1].endswith(".yml")):
                    task_text = parts[0]
                    yaml_path_str = parts[1]
                elif arg.endswith(".yaml") or arg.endswith(".yml"):
                    task_text = "Execute pipeline"
                    yaml_path_str = arg
                else:
                    # last token is file, rest is task
                    yaml_path_str = parts[-1]
                    task_text = parts[0] if len(parts) > 1 else "Execute pipeline"

                yaml_file = Path(yaml_path_str)
                if not yaml_file.exists():
                    return f"YAML file not found: `{yaml_path_str}`"
                try:
                    yaml_str = yaml_file.read_text(encoding="utf-8")
                except OSError as exc:
                    return f"Failed to read pipeline file: {exc}"

            pipeline_obj = AgentPipeline()
            try:
                pipeline_obj.load(yaml_str)
            except ValueError as exc:
                return f"Pipeline YAML error: {exc}"

            # confirm_fn for checkpoints — auto-accept in non-interactive contexts
            async def _confirm(step_name: str, results_so_far: dict) -> bool:
                # Store paused state for /pipeline resume
                registry._pipeline_state = {"yaml_str": yaml_str, "task": task_text}  # type: ignore[assignment]
                return False  # pause; user runs /pipeline resume to continue

            result = await pipeline_obj.run(task_text, registry._session, confirm_fn=_confirm)

            if result.checkpoint and result.checkpoint.paused:
                lines_out = [_format_pipeline_result(result)]
                lines_out.append(
                    f"\n**Pipeline paused at checkpoint `{result.checkpoint.step_name}`.**\n"
                    "Run `/pipeline resume` to continue."
                )
                return "\n".join(lines_out)

            return _format_pipeline_result(result)

        def _format_pipeline_result(result: "Any") -> str:
            from lidco.agents.pipeline import PipelineResult
            if not isinstance(result, PipelineResult):
                return str(result)
            lines: list[str] = ["## Pipeline Result\n"]
            for sr in result.steps:
                if sr.skipped:
                    lines.append(f"- **{sr.name}** — ⏭ skipped (condition)")
                elif sr.success:
                    preview = sr.output[:300] + ("..." if len(sr.output) > 300 else "")
                    lines.append(f"- **{sr.name}** [{sr.agent or 'checkpoint'}] ✓")
                    if preview:
                        lines.append(f"  {preview}")
                else:
                    lines.append(f"- **{sr.name}** [{sr.agent}] ✗ {sr.error}")
            status = "✓ Success" if result.success else "✗ Failed"
            lines.append(f"\n**{status}** ({len(result.steps)} steps)")
            return "\n".join(lines)

        self.register(SlashCommand("pipeline", "Run a declarative YAML agent pipeline", pipeline_handler))

        # ── Q58 Task 391: /broadcast ──────────────────────────────────────────
        async def broadcast_handler(arg: str = "", **_: Any) -> str:
            """Send a message to all registered agents simultaneously.

            /broadcast <message>
            /broadcast --agents coder,tester <message>
            """
            if not registry._session:
                return "Session not initialized."

            msg = (arg or "").strip()
            agent_names: list[str] = []

            if msg.startswith("--agents "):
                rest = msg[len("--agents "):].strip()
                if " " in rest:
                    agents_str, msg = rest.split(" ", 1)
                    msg = msg.strip()
                else:
                    agents_str, msg = rest, ""
                agent_names = [a.strip() for a in agents_str.split(",") if a.strip()]

            if not msg:
                return (
                    "Usage: `/broadcast <message>` or "
                    "`/broadcast --agents coder,tester <message>`"
                )

            reg = registry._session.agent_registry
            if not agent_names:
                agent_names = [a.name for a in reg.list_agents()] if reg else []

            if not agent_names:
                return "No agents registered."

            async def _run_one(name: str) -> tuple[str, str]:
                try:
                    context = registry._session.get_full_context() if hasattr(registry._session, "get_full_context") else ""
                    response = await registry._session.orchestrator.handle(
                        msg, agent_name=name, context=context
                    )
                    content = response.content if hasattr(response, "content") else str(response)
                    return name, content
                except Exception as exc:
                    return name, f"ERROR: {exc}"

            import asyncio as _aio
            raw_results = await _aio.gather(*(_run_one(name) for name in agent_names))

            # Deduplicate findings: extract bullet lines, drop near-duplicates (same first 40 chars)
            all_findings: list[tuple[str, str]] = []  # (agent, finding)
            for agent_name, text in raw_results:
                for line in text.splitlines():
                    stripped = line.strip()
                    if stripped.startswith(("-", "*", "•")) or stripped.startswith(tuple("123456789")):
                        all_findings.append((agent_name, stripped))

            seen_prefixes: set[str] = set()
            unique_findings: list[tuple[str, str]] = []
            for agent_name, finding in all_findings:
                prefix = finding[:40]
                if prefix not in seen_prefixes:
                    seen_prefixes.add(prefix)
                    unique_findings.append((agent_name, finding))

            lines: list[str] = [f"## Broadcast: `{msg[:60]}`\n"]

            if unique_findings:
                lines.append("### Aggregated Findings (deduplicated)\n")
                by_agent: dict[str, list[str]] = {}
                for a, f in unique_findings:
                    by_agent.setdefault(a, []).append(f)
                for name in agent_names:
                    if name in by_agent:
                        lines.append(f"**{name}:**")
                        for finding in by_agent[name]:
                            lines.append(f"  {finding}")
                lines.append("")
            else:
                # Fallback: show full responses
                for a_name, text in raw_results:
                    preview = text[:400] + ("..." if len(text) > 400 else "")
                    lines.append(f"**{a_name}:**\n{preview}\n")

            return "\n".join(lines)

        self.register(SlashCommand("broadcast", "Send task to all agents simultaneously", broadcast_handler))

        # ── Q58 Task 392: extend /agents with stats subcommand ────────────────
        # We store the enhanced handler; patch the registered command after
        _orig_agents_handler = self._commands.get("agents")

        async def agents_with_stats_handler(arg: str = "", **_: Any) -> str:
            """Extended /agents with stats subcommand.

            /agents              — list agents
            /agents stats        — performance leaderboard
            /agents stats --period 7d
            /agents bg           — background tasks
            /agents inspect <n>  — agent details
            """
            raw = (arg or "").strip()

            # /agents stats [--period Nd]
            if raw == "stats" or raw.startswith("stats"):
                stats = registry._agent_stats
                if not stats:
                    return "No agent stats recorded yet."

                # Parse --period flag (approximate: all stats if not filterable)
                _period_days: int | None = None
                if "--period" in raw:
                    try:
                        period_part = raw.split("--period")[1].strip().split()[0]
                        if period_part.endswith("d"):
                            _period_days = int(period_part[:-1])
                    except (IndexError, ValueError):
                        pass

                rows: list[tuple[str, int, float, int, float]] = []
                for name, info in stats.items():
                    call_count = int(info.get("call_count", 0))
                    total_elapsed = float(info.get("total_elapsed", 0.0))
                    total_tokens = int(info.get("total_tokens", 0))
                    success_count = int(info.get("success_count", call_count))
                    avg_elapsed = total_elapsed / call_count if call_count else 0.0
                    success_rate = success_count / call_count if call_count else 1.0
                    rows.append((name, call_count, avg_elapsed, total_tokens, success_rate))

                # Sort by call count desc
                rows.sort(key=lambda r: r[1], reverse=True)

                lines: list[str] = ["## Agent Performance Leaderboard\n"]
                header = f"{'Agent':<16} {'Calls':>6} {'Avg(s)':>8} {'Tokens':>8} {'Success':>8}"
                lines.append(f"```\n{header}")
                lines.append("-" * len(header))
                for name, calls, avg_s, tokens, rate in rows:
                    lines.append(
                        f"{name:<16} {calls:>6} {avg_s:>8.2f} {tokens:>8} {rate:>7.0%}"
                    )
                lines.append("```")
                if _period_days:
                    lines.append(f"\n_Period filter: last {_period_days}d (approximate — all available data shown)_")
                return "\n".join(lines)

            # Delegate to original handler
            if _orig_agents_handler:
                return await _orig_agents_handler.handler(arg=arg)
            return "Session not initialized."

        self.register(SlashCommand("agents", "List agents, view stats, manage background tasks", agents_with_stats_handler))

        # Task 295/296: auto-load custom commands from commands.yaml
        # and register discovered skills as /<name> slash commands
        self._load_skill_commands(_get_skill_registry)

    def _load_skill_commands(self, get_registry: Any) -> None:
        """Register discovered skills and custom commands as slash commands."""
        # Custom commands from .lidco/commands.yaml (Task 296)
        try:
            from lidco.skills.custom_commands import load_custom_commands
            for cmd in load_custom_commands():
                if self._commands.get(cmd.name):
                    continue  # don't override built-ins

                async def _make_handler(c: Any = cmd) -> Any:
                    async def handler(arg: str = "", **_: Any) -> str:
                        session = self._session
                        prompt = c.render(arg)
                        if not prompt:
                            return f"Custom command `/{c.name}` has no prompt configured."
                        try:
                            response = await session.orchestrator.handle(
                                prompt, agent_name=c.agent
                            )
                            return response.content if hasattr(response, "content") else str(response)
                        except Exception as exc:
                            return f"Command `/{c.name}` failed: {exc}"
                    return handler

                import asyncio as _asyncio
                handler_fn = _asyncio.coroutine(_make_handler.__wrapped__ if hasattr(_make_handler, "__wrapped__") else None) if False else None

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

        # ── Q59 — Code Execution & Runtime (Tasks 396–402) ───────────────────
        registry = self  # alias used by Q59 handlers

        # Task 396: /run [python|bash|js] <code> — execute code snippet
        async def repl_run_handler(arg: str = "", **_: Any) -> str:
            """/run [python|bash|js] <code|```block>  — execute a code snippet."""
            import re as _re
            from lidco.tools.code_runner import CodeRunner, RunResult

            if not arg.strip():
                return (
                    "**Usage:** `/run [python|bash|js] <code>`\n\n"
                    "Executes a code snippet and shows output.\n\n"
                    "**Examples:**\n"
                    "- `/run python print('hello')`\n"
                    "- `/run bash ls -la`\n"
                    "- `/run js console.log(1+1)`"
                )

            # Detect language from fenced code block
            block_match = _re.match(r"```(\w+)?\n?(.*?)```", arg.strip(), _re.DOTALL)
            if block_match:
                lang_hint = (block_match.group(1) or "").lower()
                code = block_match.group(2)
            else:
                # Split language token from rest
                parts_arg = arg.strip().split(None, 1)
                if len(parts_arg) >= 2 and parts_arg[0].lower() in ("python", "bash", "js", "javascript"):
                    lang_hint = parts_arg[0].lower()
                    code = parts_arg[1]
                else:
                    lang_hint = "python"
                    code = arg.strip()

            if lang_hint == "javascript":
                lang_hint = "js"
            if lang_hint not in ("python", "bash", "js"):
                lang_hint = "python"

            runner = CodeRunner()
            if lang_hint == "python":
                result: RunResult = runner.run_python(code)
            elif lang_hint == "bash":
                result = runner.run_bash(code)
            else:
                result = runner.run_js(code)

            rc_label = "OK" if result.returncode == 0 else f"exit {result.returncode}"
            header = f"**[{lang_hint}]** `{rc_label}` — {result.elapsed:.2f}s\n\n"
            parts_out: list[str] = []
            if result.stdout.strip():
                parts_out.append(f"```\n{result.stdout.rstrip()}\n```")
            if result.stderr.strip():
                parts_out.append(f"**stderr:**\n```\n{result.stderr.rstrip()}\n```")
            if not parts_out:
                parts_out.append("_(no output)_")
            return header + "\n".join(parts_out)

        self.register(SlashCommand("run", "Execute code snippet in REPL [python|bash|js]", repl_run_handler))

        # Task 397: /debug run <file> [args...]  — extend existing /debug handler
        _orig_debug_cmd = self.get("debug")

        async def debug_extended_handler(arg: str = "", **kw: Any) -> str:
            """/debug — extends original debug with `run <file>` subcommand."""
            import asyncio as _asyncio
            import subprocess as _subprocess

            if arg.startswith("run ") or arg == "run":
                rest = arg[4:].strip()
                if not rest:
                    return "**Usage:** `/debug run <file.py> [args...]`"

                file_parts = rest.split()
                file_path = file_parts[0]
                extra_args = file_parts[1:]

                # Syntax check first
                try:
                    syntax_proc = _subprocess.run(
                        ["python", "-m", "py_compile", file_path],
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )
                except Exception as exc:
                    return f"Syntax check failed: {exc}"

                if syntax_proc.returncode != 0:
                    err = syntax_proc.stderr or syntax_proc.stdout
                    return f"**Syntax error in `{file_path}`:**\n\n```\n{err.strip()}\n```"

                # Run the file
                cmd_dbg = ["python", file_path] + extra_args
                try:
                    run_proc = await _asyncio.create_subprocess_exec(
                        *cmd_dbg,
                        stdout=_asyncio.subprocess.PIPE,
                        stderr=_asyncio.subprocess.PIPE,
                    )
                    stdout_b, stderr_b = await _asyncio.wait_for(run_proc.communicate(), timeout=60)
                except _asyncio.TimeoutError:
                    return "Execution timed out after 60s."
                except Exception as exc:
                    return f"Execution error: {exc}"

                stdout_dbg = stdout_b.decode("utf-8", errors="replace")
                stderr_dbg = stderr_b.decode("utf-8", errors="replace")
                rc_dbg = run_proc.returncode or 0

                dbg_lines: list[str] = []
                dbg_lines.append(f"**`python {' '.join([file_path] + extra_args)}`** — exit {rc_dbg}")
                if stdout_dbg.strip():
                    dbg_lines.append(f"\n**stdout:**\n```\n{stdout_dbg.strip()}\n```")
                if stderr_dbg.strip():
                    dbg_lines.append(f"\n**stderr:**\n```\n{stderr_dbg.strip()}\n```")

                if rc_dbg != 0 and registry._session:
                    session = registry._session
                    analysis_prompt = (
                        f"The script `{file_path}` exited with code {rc_dbg}.\n\n"
                        f"stderr:\n```\n{stderr_dbg.strip()}\n```\n\n"
                        "Briefly explain what went wrong and suggest a fix."
                    )
                    try:
                        resp = await session.orchestrator.handle(analysis_prompt, agent_name="debugger")
                        suggestion = resp.content if hasattr(resp, "content") else str(resp)
                        dbg_lines.append(f"\n**AI suggestion:**\n{suggestion}")
                    except Exception:
                        pass

                return "\n".join(dbg_lines)

            # Delegate to original handler
            if _orig_debug_cmd:
                return await _orig_debug_cmd.handler(arg=arg, **kw)
            return "debug handler not found"

        self.register(SlashCommand("debug", "Toggle debug mode / run file: /debug [on|off|run <file>|kb|stats|preset]", debug_extended_handler))

        # Task 398: /test [path] [-k filter] [--watch]
        async def test_handler(arg: str = "", **_: Any) -> str:
            """/test [path] [-k filter] [--watch] — run pytest from REPL."""
            import asyncio as _asyncio
            import re as _re
            import time as _time

            if not arg.strip():
                return (
                    "**Usage:** `/test [path] [-k filter] [--watch]`\n\n"
                    "Runs pytest and shows results.\n\n"
                    "**Examples:**\n"
                    "- `/test tests/unit/`\n"
                    "- `/test tests/ -k test_auth`\n"
                    "- `/test --watch`"
                )

            watch_mode = "--watch" in arg
            arg_clean = arg.replace("--watch", "").strip()

            cmd_parts = ["python", "-m", "pytest"]
            if arg_clean:
                cmd_parts += arg_clean.split()
            cmd_parts += ["-v", "--tb=short", "-q"]

            project_dir = None
            if registry._session:
                project_dir = str(registry._session.project_dir)

            async def _run_once() -> str:
                try:
                    proc = await _asyncio.create_subprocess_exec(
                        *cmd_parts,
                        stdout=_asyncio.subprocess.PIPE,
                        stderr=_asyncio.subprocess.STDOUT,
                        cwd=project_dir,
                    )
                    output_b, _ = await _asyncio.wait_for(proc.communicate(), timeout=300)
                except _asyncio.TimeoutError:
                    return "Tests timed out after 300s."
                except Exception as exc:
                    return f"Test run failed: {exc}"

                output_t = output_b.decode("utf-8", errors="replace")
                rc_t = proc.returncode or 0

                passed = 0
                failed = 0
                errors_count = 0
                summary_match = _re.search(r"(\d+) passed", output_t)
                if summary_match:
                    passed = int(summary_match.group(1))
                fail_match = _re.search(r"(\d+) failed", output_t)
                if fail_match:
                    failed = int(fail_match.group(1))
                err_match = _re.search(r"(\d+) error", output_t)
                if err_match:
                    errors_count = int(err_match.group(1))

                status_t = "PASSED" if rc_t == 0 else "FAILED"
                header_t = f"**pytest {status_t}** — {passed} passed, {failed} failed, {errors_count} errors\n\n"

                lines_all = output_t.splitlines()
                display_t = "\n".join(lines_all[-80:]) if len(lines_all) > 80 else output_t
                result_str = header_t + f"```\n{display_t}\n```"

                if rc_t != 0 and registry._session:
                    try:
                        session = registry._session
                        prompt_t = (
                            f"pytest run failed:\n\n```\n{output_t[-2000:]}\n```\n\n"
                            "Briefly summarize the failures and suggest fixes."
                        )
                        resp_t = await session.orchestrator.handle(prompt_t, agent_name="tester")
                        suggestion_t = resp_t.content if hasattr(resp_t, "content") else str(resp_t)
                        result_str += f"\n\n**AI analysis:**\n{suggestion_t}"
                    except Exception:
                        pass

                return result_str

            if not watch_mode:
                return await _run_once()

            # Watch mode: re-run on file changes (poll 3s, max 60s)
            results_list: list[str] = [await _run_once()]
            deadline = _time.monotonic() + 60

            def _snapshot_files() -> dict[str, float]:
                snap: dict[str, float] = {}
                base = Path(project_dir) if project_dir else Path(".")
                try:
                    for p in base.rglob("*.py"):
                        try:
                            snap[str(p)] = p.stat().st_mtime
                        except OSError:
                            pass
                except Exception:
                    pass
                return snap

            baseline_snap = _snapshot_files()
            while _time.monotonic() < deadline:
                await _asyncio.sleep(3)
                current_snap = _snapshot_files()
                if current_snap != baseline_snap:
                    baseline_snap = current_snap
                    results_list.append(await _run_once())

            return f"**Watch mode (ran {len(results_list)} time(s)):**\n\n" + "\n\n---\n\n".join(results_list[-3:])

        self.register(SlashCommand("test", "Run pytest from REPL: /test [path] [-k filter] [--watch]", test_handler))

        # Task 400: /venv — virtual environment manager
        async def venv_handler(arg: str = "", **_: Any) -> str:
            """/venv [create <name>|list|delete <name>|activate <name>]"""
            from lidco.tools.venv_manager import VenvManager

            base_dir = Path(".lidco") / "venvs"
            if registry._session:
                base_dir = Path(str(registry._session.project_dir)) / ".lidco" / "venvs"

            mgr = VenvManager()
            parts_v = arg.strip().split(None, 1)
            sub_v = parts_v[0].lower() if parts_v else "list"
            rest_v = parts_v[1].strip() if len(parts_v) > 1 else ""

            if sub_v == "create":
                if not rest_v:
                    return "**Usage:** `/venv create <name>`"
                try:
                    info = mgr.create(rest_v, base_dir)
                    activate = mgr.get_activate_path(info)
                    return (
                        f"**Venv `{rest_v}` created** at `{info.path}`\n\n"
                        f"Python: `{info.python_version}` | Size: `{info.size_mb} MB`\n\n"
                        f"Activate with: `source {activate}`"
                    )
                except Exception as exc:
                    return f"Failed to create venv: {exc}"

            elif sub_v == "list":
                venvs = mgr.list_venvs(base_dir)
                if not venvs:
                    return f"No virtual environments found in `{base_dir}`."
                lines_v = ["**Virtual environments:**\n"]
                for v in venvs:
                    lines_v.append(f"- `{v.name}` — Python {v.python_version}, {v.size_mb} MB")
                return "\n".join(lines_v)

            elif sub_v == "delete":
                if not rest_v:
                    return "**Usage:** `/venv delete <name>`"
                if mgr.delete(rest_v, base_dir):
                    return f"Venv `{rest_v}` deleted."
                return f"Venv `{rest_v}` not found."

            elif sub_v == "activate":
                if not rest_v:
                    return "**Usage:** `/venv activate <name>`"
                venvs = mgr.list_venvs(base_dir)
                target_v = next((v for v in venvs if v.name == rest_v), None)
                if not target_v:
                    return f"Venv `{rest_v}` not found. Run `/venv list` to see available venvs."
                activate = mgr.get_activate_path(target_v)
                return (
                    f"**Activation hint for `{rest_v}`:**\n\n"
                    f"```bash\nsource {activate}\n```"
                )

            return (
                "**Usage:** `/venv [create <name>|list|delete <name>|activate <name>]`\n\n"
                f"Venvs stored in `{base_dir}`"
            )

        self.register(SlashCommand("venv", "Manage Python virtual environments", venv_handler))

        # Task 401: /install <package> [--explain] [--no-confirm]
        async def install_handler(arg: str = "", **_: Any) -> str:
            """/install <package> [--explain] [--no-confirm]"""
            import asyncio as _asyncio
            import subprocess as _subprocess

            if not arg.strip():
                return (
                    "**Usage:** `/install <package> [--explain] [--no-confirm]`\n\n"
                    "Installs a Python package with optional AI guidance.\n\n"
                    "**Examples:**\n"
                    "- `/install requests`\n"
                    "- `/install numpy --explain`\n"
                    "- `/install pytest --no-confirm`"
                )

            explain = "--explain" in arg
            no_confirm = "--no-confirm" in arg
            pkg_tokens = arg.replace("--explain", "").replace("--no-confirm", "").strip().split()
            if not pkg_tokens:
                return "Please specify a package name."
            package = pkg_tokens[0]

            result_lines_i: list[str] = []

            # Check if already in requirements
            already_listed = False
            for req_file in ("requirements.txt", "pyproject.toml"):
                req_path = Path(req_file)
                if registry._session:
                    req_path = Path(str(registry._session.project_dir)) / req_file
                if req_path.exists():
                    content = req_path.read_text()
                    if package.lower() in content.lower():
                        already_listed = True
                        result_lines_i.append(f"**Note:** `{package}` is already listed in `{req_file}`.")
                        break

            # AI explanation
            if explain and registry._session:
                try:
                    session = registry._session
                    prompt_i = (
                        f"The user wants to install Python package `{package}`. "
                        "Briefly explain: 1) what it's used for, 2) any notable alternatives, "
                        "3) any known security or compatibility concerns (2-3 sentences total)."
                    )
                    resp_i = await session.orchestrator.handle(prompt_i, agent_name="architect")
                    explanation = resp_i.content if hasattr(resp_i, "content") else str(resp_i)
                    result_lines_i.append(f"**About `{package}`:**\n{explanation}")
                except Exception:
                    pass

            # Confirm unless --no-confirm
            if not no_confirm:
                result_lines_i.append(
                    f"\nWill run: `pip install {package}`\n\n"
                    "_Pass `--no-confirm` to skip this prompt, or confirm by running:_\n"
                    f"`/install {package} --no-confirm`"
                )
                return "\n".join(result_lines_i)

            # Run pip install
            result_lines_i.append(f"**Installing `{package}`...**")
            try:
                proc_i = await _asyncio.create_subprocess_exec(
                    "pip", "install", package,
                    stdout=_asyncio.subprocess.PIPE,
                    stderr=_asyncio.subprocess.STDOUT,
                )
                output_i_b, _ = await _asyncio.wait_for(proc_i.communicate(), timeout=120)
                output_i = output_i_b.decode("utf-8", errors="replace")
                rc_i = proc_i.returncode or 0
            except _asyncio.TimeoutError:
                return "pip install timed out after 120s."
            except Exception as exc:
                return f"pip install failed: {exc}"

            status_i = "succeeded" if rc_i == 0 else f"failed (exit {rc_i})"
            result_lines_i.append(f"**pip install {status_i}:**\n```\n{output_i[-1000:].strip()}\n```")

            if rc_i == 0 and not already_listed:
                result_lines_i.append(
                    f"\n_Run `/install {package} --no-confirm` added. "
                    "Consider adding it manually to `requirements.txt`._"
                )

            return "\n".join(result_lines_i)

        self.register(SlashCommand("install", "Install Python package with AI guidance", install_handler))

        # Task 402: /diff-output <command>
        self._output_differ_baseline: dict[str, str] = {}  # type: ignore[attr-defined]

        async def diff_output_handler(arg: str = "", **_: Any) -> str:
            """/diff-output <command> — capture output and diff before/after."""
            from lidco.tools.output_differ import OutputDiffer

            if not arg.strip():
                return (
                    "**Usage:** `/diff-output <command>`\n\n"
                    "First call captures the **before** baseline.\n"
                    "Second call runs the command again and shows the diff.\n\n"
                    "**Example:**\n"
                    "- `/diff-output python --version`"
                )

            command_d = arg.strip()
            differ = OutputDiffer()

            if command_d not in self._output_differ_baseline:
                baseline_d = differ.capture(command_d)
                self._output_differ_baseline[command_d] = baseline_d
                preview = baseline_d[:300] + ("..." if len(baseline_d) > 300 else "")
                return (
                    f"**Baseline captured** for `{command_d}`\n\n"
                    f"```\n{preview}\n```\n\n"
                    "_Run the same command again after making changes to see the diff._"
                )

            before_d = self._output_differ_baseline.pop(command_d)
            after_d = differ.capture(command_d)
            result_d = differ.diff(before_d, after_d)

            if not result_d.changed:
                return f"**No changes** in output of `{command_d}`."

            summary_d = f"+{result_d.added_lines} lines / -{result_d.removed_lines} lines"
            diff_display = result_d.diff_text[:2000]
            if len(result_d.diff_text) > 2000:
                diff_display += "\n... (truncated)"
            return (
                f"**Output diff for `{command_d}`** — {summary_d}\n\n"
                f"```diff\n{diff_display}\n```"
            )

        self.register(SlashCommand("diff-output", "Compare command output before/after changes", diff_output_handler))

        # ── Q63 Task 423: /think ───────────────────────────────────────────────

        async def think_handler(arg: str = "", **_: Any) -> str:
            """/think [on|off|budget N] — toggle extended thinking or set token budget."""
            if not registry._session:
                return "Session not initialized."

            cfg = registry._session.config.agents
            text = arg.strip().lower()

            if not text or text == "status":
                state = "on" if cfg.extended_thinking else "off"
                return (
                    f"**Extended thinking:** {state}\n"
                    f"**Budget:** {cfg.thinking_budget} tokens\n\n"
                    "Usage: `/think on|off` or `/think budget <N>`"
                )

            parts = text.split()

            if parts[0] == "on":
                registry._session.config = registry._session.config.model_copy(
                    update={"agents": cfg.model_copy(update={"extended_thinking": True})}
                )
                return f"Extended thinking **enabled** (budget: {cfg.thinking_budget} tokens)."

            if parts[0] == "off":
                registry._session.config = registry._session.config.model_copy(
                    update={"agents": cfg.model_copy(update={"extended_thinking": False})}
                )
                return "Extended thinking **disabled**."

            if parts[0] == "budget" and len(parts) >= 2:
                try:
                    budget = int(parts[1].replace("k", "000").replace("K", "000"))
                    registry._session.config = registry._session.config.model_copy(
                        update={"agents": cfg.model_copy(update={"thinking_budget": budget})}
                    )
                    return f"Thinking budget set to **{budget:,}** tokens."
                except ValueError:
                    return f"Invalid budget value: `{parts[1]}`."

            return (
                "**Usage:** `/think [on|off|budget N]`\n\n"
                "  `on`        — enable extended thinking\n"
                "  `off`       — disable extended thinking\n"
                "  `budget N`  — set thinking token budget (e.g. `budget 8000`)\n"
                "  `status`    — show current settings"
            )

        self.register(SlashCommand(
            "think",
            "Toggle extended thinking: /think [on|off|budget N]",
            think_handler,
        ))

        # ── Q63 Task 425: /warm ────────────────────────────────────────────────

        async def warm_handler(arg: str = "", **_: Any) -> str:
            """/warm [all|<agent>] — pre-warm Anthropic prompt cache."""
            if not registry._session:
                return "Session not initialized."

            from lidco.ai.cache_warm import CacheWarmer
            warmer = CacheWarmer(registry._session)

            text = arg.strip()
            if not text or text == "all":
                results = await warmer.warm_all()
            else:
                results = await warmer.warm_all(agent_names=[text])

            if not results:
                return "No agents to warm."

            lines = ["**Cache Warm Results**\n"]
            for r in results:
                if r.success:
                    lines.append(
                        f"  ✓ **{r.agent_name}** — {r.tokens_cached} tokens cached "
                        f"({r.duration_ms:.0f}ms)"
                    )
                else:
                    lines.append(f"  ✗ **{r.agent_name}** — {r.error}")

            total_cached = sum(r.tokens_cached for r in results if r.success)
            lines.append(f"\nTotal tokens cached: **{total_cached}**")
            return "\n".join(lines)

        self.register(SlashCommand(
            "warm",
            "Pre-warm prompt cache: /warm [all|<agent>]",
            warm_handler,
        ))

        # ── Q63 Task 426: /compare-models ──────────────────────────────────────

        async def compare_models_handler(arg: str = "", **_: Any) -> str:
            """/compare-models <m1> <m2> [--prompt "..."] — compare models side by side."""
            import re as _re
            if not registry._session:
                return "Session not initialized."

            if not arg.strip():
                return (
                    "**Usage:** `/compare-models <model1> <model2> [--prompt \"...\"]`\n\n"
                    "Example: `/compare-models gpt-4o claude-3-5-sonnet --prompt \"Explain recursion\"`"
                )

            # Extract --prompt flag
            prompt = "Explain the concept of recursion in programming."
            m = _re.search(r'--prompt\s+"([^"]+)"', arg)
            if not m:
                m = _re.search(r"--prompt\s+'([^']+)'", arg)
            if not m:
                m = _re.search(r"--prompt\s+(\S.*?)(?:\s+--|$)", arg)
            if m:
                prompt = m.group(1).strip()
                arg = arg[:m.start()].strip() + arg[m.end():].strip()

            models = [m2.strip() for m2 in arg.split() if m2.strip()]
            if len(models) < 1:
                return "Please provide at least one model name."

            from lidco.ai.cost_compare import ModelComparator
            comparator = ModelComparator(registry._session)
            results = await comparator.compare(prompt, models)

            lines = [f"**Model Comparison**", f"Prompt: *{prompt[:80]}{'…' if len(prompt) > 80 else ''}*", ""]
            lines.append(comparator.format_table(results))
            return "\n".join(lines)

        self.register(SlashCommand(
            "compare-models",
            "Compare LLM models side-by-side: /compare-models <m1> <m2> [--prompt \"...\"]",
            compare_models_handler,
        ))

        # ── Q63 Task 427: /ollama ──────────────────────────────────────────────

        async def ollama_handler(arg: str = "", **_: Any) -> str:
            """/ollama [list|pull <model>|run <model>] — manage local Ollama models."""
            from lidco.ai.ollama_provider import OllamaProvider

            base_url = "http://localhost:11434"
            if registry._session:
                base_url = getattr(
                    registry._session.config.llm, "ollama_base_url", base_url
                )

            provider = OllamaProvider(base_url)
            text = arg.strip()

            if not text or text == "list":
                if not provider.is_available():
                    return (
                        "Ollama is not running at `{}`.\n\n"
                        "Start Ollama with: `ollama serve`".format(base_url)
                    )
                models = provider.list_models()
                if not models:
                    return "No models installed. Use `ollama pull <model>` to install one."
                lines = [f"**Ollama models** ({len(models)} installed)\n"]
                for m in models:
                    lines.append(f"  · {m}")
                return "\n".join(lines)

            parts = text.split(None, 1)
            subcmd = parts[0].lower()
            rest = parts[1].strip() if len(parts) > 1 else ""

            if subcmd == "pull":
                if not rest:
                    return "Usage: `/ollama pull <model-name>`"
                return (
                    f"To pull **{rest}**, run in your terminal:\n\n"
                    f"```\nollama pull {rest}\n```"
                )

            if subcmd == "run":
                if not rest:
                    return "Usage: `/ollama run <model-name>`"
                if not provider.is_available():
                    return "Ollama is not running. Start with: `ollama serve`"
                try:
                    response = await provider.chat(
                        messages=[{"role": "user", "content": "Hello"}],
                        model=rest,
                    )
                    return f"**{rest}** responded:\n\n{response}"
                except Exception as e:
                    return f"Error running `{rest}`: {e}"

            return (
                "**Usage:** `/ollama <subcommand>`\n\n"
                "  `list`        — list installed models\n"
                "  `pull <name>` — show pull command\n"
                "  `run <name>`  — test model with a ping"
            )

        self.register(SlashCommand(
            "ollama",
            "Manage local Ollama models: /ollama [list|pull <model>|run <model>]",
            ollama_handler,
        ))

        # ── Q63 Task 429: /cost-budget ─────────────────────────────────────────

        # Shared BudgetTracker instance persisted on CommandRegistry
        self._cost_budget_tracker: Any = None

        async def cost_budget_handler(arg: str = "", **_: Any) -> str:
            """/cost-budget [status|reset|set daily N|set monthly N] — manage cost budget."""
            from lidco.ai.budget_alerts import BudgetTracker

            if registry._cost_budget_tracker is None:
                daily = 5.0
                monthly = 50.0
                if registry._session:
                    cfg = registry._session.config
                    budget_cfg = getattr(cfg, "budget", None)
                    if budget_cfg:
                        daily = getattr(budget_cfg, "daily_usd", daily)
                        monthly = getattr(budget_cfg, "monthly_usd", monthly)
                registry._cost_budget_tracker = BudgetTracker(
                    daily_limit_usd=daily,
                    monthly_limit_usd=monthly,
                )

            tracker: BudgetTracker = registry._cost_budget_tracker
            text = arg.strip().lower()
            parts = text.split()

            if not text or text == "status":
                st = tracker.status()
                lines = ["**Cost Budget Status**\n"]
                lines.append(
                    f"  Daily:   ${st['daily_spend']:.4f} / ${st['daily_limit']:.2f}"
                    f"  ({st['daily_pct']:.1f}%)"
                )
                lines.append(
                    f"  Monthly: ${st['monthly_spend']:.4f} / ${st['monthly_limit']:.2f}"
                    f"  ({st['monthly_pct']:.1f}%)"
                )
                alerts = tracker.check_limits()
                if alerts:
                    lines.append("")
                    for a in alerts:
                        lines.append(f"  ⚠ {a}")
                return "\n".join(lines)

            if text == "reset":
                tracker.reset_all()
                return "Budget counters reset."

            if len(parts) >= 3 and parts[0] == "set":
                period = parts[1]
                try:
                    amount = float(parts[2])
                except ValueError:
                    return f"Invalid amount: `{parts[2]}`."
                if period == "daily":
                    tracker.daily_limit_usd = amount
                    return f"Daily budget set to **${amount:.2f}**."
                if period == "monthly":
                    tracker.monthly_limit_usd = amount
                    return f"Monthly budget set to **${amount:.2f}**."
                return f"Unknown period `{period}`. Use `daily` or `monthly`."

            return (
                "**Usage:** `/cost-budget [subcommand]`\n\n"
                "  `status`           — show current spend vs limits\n"
                "  `reset`            — clear all counters\n"
                "  `set daily N`      — set daily limit in USD\n"
                "  `set monthly N`    — set monthly limit in USD"
            )

        self.register(SlashCommand(
            "cost-budget",
            "Manage LLM cost budget alerts: /cost-budget [status|reset|set daily N|set monthly N]",
            cost_budget_handler,
        ))

        # ── Q60: External Integrations ─────────────────────────────────────

        # Task 403: /issue — GitHub Issues integration
        async def issue_handler(arg: str = "", **_: Any) -> str:
            """/issue list|view N|create|close N — GitHub Issues integration."""
            from lidco.integrations.github_issues import IssueClient

            client = IssueClient()
            parts = (arg or "").split(None, 1)
            sub = parts[0].lower() if parts else "list"
            rest = parts[1].strip() if len(parts) > 1 else ""

            try:
                if sub == "list" or not sub:
                    issues = client.list_issues()
                    if not issues:
                        return "No open issues found."
                    lines = [f"**Open Issues ({len(issues)})**\n"]
                    for iss in issues:
                        label_str = f" [{', '.join(iss.labels)}]" if iss.labels else ""
                        lines.append(f"- #{iss.number} **{iss.title}**{label_str}")
                    return "\n".join(lines)

                if sub == "view":
                    if not rest.isdigit():
                        return "Usage: `/issue view <number>`"
                    iss = client.get_issue(int(rest))
                    lines = [
                        f"## Issue #{iss.number}: {iss.title}",
                        f"**State:** {iss.state}  |  **URL:** {iss.url}",
                    ]
                    if iss.labels:
                        lines.append(f"**Labels:** {', '.join(iss.labels)}")
                    if iss.body:
                        lines.append(f"\n{iss.body[:2000]}")
                    return "\n".join(lines)

                if sub == "create":
                    if not rest:
                        return "Usage: `/issue create <title>`"
                    iss = client.create_issue(title=rest)
                    return f"Created issue #{iss.number}: **{iss.title}**\n{iss.url}"

                if sub == "close":
                    if not rest.isdigit():
                        return "Usage: `/issue close <number>`"
                    client.close_issue(int(rest))
                    return f"Closed issue #{rest}."

                return (
                    "**GitHub Issues commands:**\n\n"
                    "- `/issue list` — list open issues\n"
                    "- `/issue view N` — view issue #N\n"
                    "- `/issue create <title>` — create new issue\n"
                    "- `/issue close N` — close issue #N"
                )
            except RuntimeError as exc:
                return f"GitHub Issues error: {exc}"

        self.register(SlashCommand("issue", "GitHub Issues integration", issue_handler))

        # Task 404: /ci — CI/CD pipeline status
        async def ci_handler(arg: str = "", **_: Any) -> str:
            """/ci [--watch] — Show latest CI/CD workflow runs for current branch."""
            from lidco.integrations.ci_status import CIClient

            client = CIClient()
            watch = "--watch" in (arg or "")

            try:
                runs = client.get_current_branch_status(limit=5)
            except RuntimeError as exc:
                return f"CI status error: {exc}"

            if not runs:
                return "No workflow runs found for current branch."

            _STATUS_ICONS: dict = {
                "completed": {"success": "✅", "failure": "❌", "cancelled": "⊘", "skipped": "⏭"},
                "in_progress": "⟳",
                "queued": "⏳",
                "waiting": "⏳",
            }

            def _format_runs(ci_runs: list) -> str:
                lines = [f"**CI Runs** (branch: {ci_runs[0].branch})\n"]
                for run in ci_runs:
                    if run.status == "completed":
                        icon = _STATUS_ICONS["completed"].get(run.conclusion, "?")
                    else:
                        icon = _STATUS_ICONS.get(run.status, "?")
                    lines.append(
                        f"- {icon} **{run.name}** — {run.status}"
                        + (f" / {run.conclusion}" if run.conclusion else "")
                        + f"\n  `{run.url}`"
                    )
                return "\n".join(lines)

            if not watch:
                return _format_runs(runs)

            return _format_runs(runs) + "\n\n_--watch mode: re-run `/ci --watch` to refresh_"

        self.register(SlashCommand("ci", "Show CI/CD workflow run status for current branch", ci_handler))

        # Task 405: /slack — Send Slack notification
        async def slack_handler(arg: str = "", **_: Any) -> str:
            """/slack <message> — Send message to configured Slack webhook."""
            from lidco.integrations.slack import SlackNotifier

            msg = (arg or "").strip()
            if not msg:
                return (
                    "**Usage:** `/slack <message>`\n\n"
                    "Sends a message to the configured Slack webhook.\n\n"
                    "**Configuration:**\n"
                    "- Set `LIDCO_SLACK_WEBHOOK` environment variable, or\n"
                    "- Add `slack.webhook_url` to `~/.lidco/config.yaml`"
                )

            try:
                notifier = SlackNotifier()
                notifier.send(msg)
                return f"Message sent to Slack: `{msg[:100]}`"
            except ValueError as exc:
                return f"Slack not configured: {exc}"
            except RuntimeError as exc:
                return f"Slack error: {exc}"

        self.register(SlashCommand("slack", "Send Slack notification to configured webhook", slack_handler))

        # Task 406: /ticket — Linear/Jira ticket integration
        async def ticket_handler(arg: str = "", **_: Any) -> str:
            """/ticket list|view ID|update ID [--status STATUS] [--comment TEXT]"""
            import os as _os

            parts = (arg or "").split(None, 1)
            sub = parts[0].lower() if parts else "list"
            rest = parts[1] if len(parts) > 1 else ""

            has_linear = bool(_os.environ.get("LINEAR_API_KEY"))
            has_jira = bool(_os.environ.get("JIRA_URL") and _os.environ.get("JIRA_TOKEN"))

            if not has_linear and not has_jira:
                return (
                    "**Ticket client not configured.**\n\n"
                    "Set one of:\n"
                    "- `LINEAR_API_KEY` for Linear\n"
                    "- `JIRA_URL` + `JIRA_TOKEN` for Jira"
                )

            if has_linear:
                from lidco.integrations.ticket_client import LinearClient
                client_t = LinearClient()
            else:
                from lidco.integrations.ticket_client import JiraClient
                client_t = JiraClient()

            try:
                if sub == "list":
                    tickets = client_t.list_tickets()
                    if not tickets:
                        return "No tickets found."
                    lines = [f"**Tickets ({len(tickets)})**\n"]
                    for t in tickets:
                        lines.append(f"- **{t.ticket_id}** [{t.status}] {t.title}")
                    return "\n".join(lines)

                if sub == "view":
                    if not rest.strip():
                        return "Usage: `/ticket view <id>`"
                    ticket = client_t.get_ticket(rest.strip())
                    lines = [
                        f"## {ticket.ticket_id}: {ticket.title}",
                        f"**Status:** {ticket.status}",
                    ]
                    if ticket.assignee:
                        lines.append(f"**Assignee:** {ticket.assignee}")
                    if ticket.url:
                        lines.append(f"**URL:** {ticket.url}")
                    if ticket.description:
                        lines.append(f"\n{ticket.description[:1000]}")
                    return "\n".join(lines)

                if sub == "update":
                    rest_parts = rest.split()
                    if not rest_parts:
                        return "Usage: `/ticket update <id> [--status STATUS] [--comment TEXT]`"
                    ticket_id = rest_parts[0]
                    status = None
                    comment = None
                    i = 1
                    while i < len(rest_parts):
                        if rest_parts[i] == "--status" and i + 1 < len(rest_parts):
                            status = rest_parts[i + 1]
                            i += 2
                        elif rest_parts[i] == "--comment" and i + 1 < len(rest_parts):
                            comment = " ".join(rest_parts[i + 1:])
                            break
                        else:
                            i += 1
                    updated = client_t.update_ticket(ticket_id, status=status, comment=comment)
                    return f"Updated **{updated.ticket_id}**: status={updated.status}"

                return (
                    "**Ticket commands:**\n\n"
                    "- `/ticket list` — list tickets\n"
                    "- `/ticket view <id>` — view ticket\n"
                    "- `/ticket update <id> [--status STATUS] [--comment TEXT]` — update ticket"
                )
            except (ValueError, RuntimeError) as exc:
                return f"Ticket error: {exc}"

        self.register(SlashCommand("ticket", "Linear/Jira ticket integration", ticket_handler))

        # Task 407: /openapi — OpenAPI client generator
        async def openapi_handler(arg: str = "", **_: Any) -> str:
            """/openapi import path/to/spec.yaml [--output client.py]"""
            from lidco.integrations.openapi_gen import OpenAPIParser, PythonClientGenerator

            tokens = (arg or "").split()
            if not tokens or tokens[0].lower() != "import":
                return (
                    "**Usage:** `/openapi import path/to/spec.yaml [--output client.py]`\n\n"
                    "Generates a typed Python requests-based API client."
                )

            spec_parts = [p for p in tokens[1:] if not p.startswith("--")]
            output_file = None
            if "--output" in tokens:
                idx = tokens.index("--output")
                if idx + 1 < len(tokens):
                    output_file = tokens[idx + 1]
                    spec_parts = [p for p in spec_parts if p != output_file]

            if not spec_parts:
                return "No spec file provided. Usage: `/openapi import path/to/spec.yaml`"

            spec_path = spec_parts[0]
            try:
                parser = OpenAPIParser(spec_path)
                parser.load()
                gen = PythonClientGenerator()
                source = gen.generate(parser, output_file=output_file)
                endpoints = parser.extract_endpoints()
                msg_lines = [
                    f"**OpenAPI Client Generated** from `{spec_path}`",
                    f"- Title: {parser.title}",
                    f"- Endpoints: {len(endpoints)}",
                ]
                if output_file:
                    msg_lines.append(f"- Output: `{output_file}`")
                else:
                    preview = source[:1500]
                    if len(source) > 1500:
                        preview += "\n... (truncated)"
                    msg_lines.append(f"\n```python\n{preview}\n```")
                return "\n".join(msg_lines)
            except (ValueError, RuntimeError) as exc:
                return f"OpenAPI error: {exc}"

        self.register(SlashCommand("openapi", "Generate Python API client from OpenAPI spec", openapi_handler))

        # Task 408: /api — API test runner
        async def api_handler(arg: str = "", **_: Any) -> str:
            """/api [--base URL] [--header KEY:VAL] METHOD /path [--body JSON]"""
            from lidco.integrations.api_runner import APIRunner

            tokens = (arg or "").split()
            if not tokens:
                return (
                    "**Usage:** `/api [--base URL] [--header KEY:VAL] METHOD /path [--body JSON]`\n\n"
                    "**Examples:**\n"
                    "- `/api GET /users`\n"
                    "- `/api POST /users --body '{\"name\":\"Alice\"}'`\n"
                    "- `/api --base https://api.example.com GET /me`"
                )

            base_url = ""
            headers_api: dict[str, str] = {}
            body_json = None
            method = ""
            path = ""

            i = 0
            while i < len(tokens):
                t = tokens[i]
                if t == "--base" and i + 1 < len(tokens):
                    base_url = tokens[i + 1]
                    i += 2
                elif t == "--header" and i + 1 < len(tokens):
                    kv = tokens[i + 1]
                    if ":" in kv:
                        k, v = kv.split(":", 1)
                        headers_api[k.strip()] = v.strip()
                    i += 2
                elif t == "--body" and i + 1 < len(tokens):
                    body_str = " ".join(tokens[i + 1:])
                    try:
                        import json as _json_api
                        body_json = _json_api.loads(body_str)
                    except Exception:
                        body_json = body_str
                    break
                elif not method and t.upper() in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"):
                    method = t.upper()
                    i += 1
                elif method and not path:
                    path = t
                    i += 1
                else:
                    i += 1

            if not method:
                return "No HTTP method found. Use GET, POST, PUT, PATCH, or DELETE."
            if not path:
                return "No path provided."

            try:
                runner = APIRunner(base_url=base_url, headers=headers_api)
                resp = runner.request(method, path, body=body_json)
                return resp.format()
            except RuntimeError as exc:
                return f"API request failed: {exc}"

        self.register(SlashCommand("http", "Make HTTP API requests (METHOD-first format)", api_handler))

        # Task 409: /browser — Browser automation
        async def browser_handler(arg: str = "", **_: Any) -> str:
            """/browser <url> — Open browser and take screenshot via Playwright."""
            import shutil as _shutil

            url = (arg or "").strip()
            if not url:
                return (
                    "**Usage:** `/browser <url>`\n\n"
                    "Takes a screenshot of the given URL.\n\n"
                    "**Requires:** Playwright installed\n"
                    "  `pip install playwright && playwright install chromium`"
                )

            if not _shutil.which("playwright"):
                return (
                    "Playwright is not installed.\n\n"
                    "Install it with:\n"
                    "  `pip install playwright`\n"
                    "  `playwright install chromium`"
                )

            from lidco.integrations.browser import BrowserSession

            session_br = BrowserSession()
            screenshot_path = "lidco_screenshot.png"
            try:
                saved = session_br.screenshot(screenshot_path, url=url)
                return f"Screenshot of `{url}` saved to `{saved}`"
            except RuntimeError as exc:
                return f"Browser error: {exc}"

        self.register(SlashCommand("browser", "Open browser and take screenshot via Playwright", browser_handler))

        # ------------------------------------------------------------------ #
        # Q61 — Smart Proactive Assistance                                    #
        # ------------------------------------------------------------------ #

        import asyncio as _asyncio_q61

        # Task 410: /bugbot
        self._bugbot_enabled: bool = False  # type: ignore[attr-defined]

        async def bugbot_handler(arg: str = "", **_: Any) -> str:
            """/bugbot on|off|status [file] — proactive bug detection."""
            from lidco.proactive.bugbot import BugbotAnalyzer

            raw = (arg or "").strip()

            if raw in ("on", "off"):
                registry._bugbot_enabled = raw == "on"
                state = "enabled" if registry._bugbot_enabled else "disabled"
                return f"Bugbot {state}."

            if raw == "status":
                state = "enabled" if registry._bugbot_enabled else "disabled"
                return f"Bugbot is **{state}**."

            # /bugbot <file> — analyze a specific file
            if raw:
                file_path = raw
                analyzer = BugbotAnalyzer()
                try:
                    from pathlib import Path as _Path
                    source = _Path(file_path).read_text(encoding="utf-8")
                except OSError as exc:
                    return f"Cannot read `{file_path}`: {exc}"
                reports = analyzer.analyze(source, file_path)
                if not reports:
                    return f"No bugs detected in `{file_path}`."
                lines = [f"**Bugs found in `{file_path}`:** ({len(reports)} issue(s))\n"]
                for r in reports:
                    icon = {"error": "✖", "warning": "⚠", "info": "ℹ"}.get(r.severity, "•")
                    lines.append(f"  {icon} Line {r.line} `{r.kind}` — {r.message}")
                return "\n".join(lines)

            return (
                "**Usage:** `/bugbot on|off|status [file]`\n\n"
                "- `on` / `off` — enable/disable automatic file watching\n"
                "- `status` — show current state\n"
                "- `<file>` — analyze a specific file now"
            )

        self.register(SlashCommand("bugbot", "Proactive AST-based bug detector", bugbot_handler))

        # Task 411: /regcheck
        async def regcheck_handler(arg: str = "", **_: Any) -> str:
            """/regcheck <file> — run related tests to detect regressions."""
            from lidco.proactive.regression_detector import RegressionDetector

            file_path = (arg or "").strip()
            if not file_path:
                return "**Usage:** `/regcheck <file>`\n\nRun related tests to detect regressions after editing a file."

            detector = RegressionDetector()
            result = await detector.detect(file_path)

            if not result.test_files_run:
                return f"No related test files found for `{file_path}`."

            status = "✓ All passed" if result.failed == 0 else f"✖ {result.failed} failed"
            lines = [
                f"**Regression check for `{file_path}`**",
                f"Tests run: {len(result.test_files_run)} file(s) | "
                f"Passed: {result.passed} | Failed: {result.failed} | "
                f"Time: {result.duration_ms:.0f}ms",
                f"Status: {status}",
            ]
            if result.test_files_run:
                lines.append("\nTest files:")
                for tf in result.test_files_run[:5]:
                    lines.append(f"  - `{tf}`")
            return "\n".join(lines)

        self.register(SlashCommand("regcheck", "Run related tests to detect regressions", regcheck_handler))

        # Task 412: /fix
        async def fix_handler(arg: str = "", **_: Any) -> str:
            """/fix [file|all] [--lint] [--imports] [--preview] — auto-fix code issues."""
            from lidco.proactive.auto_fix import AutoFixer

            parts = (arg or "").split()
            preview = "--preview" in parts
            do_lint = "--lint" in parts or (not any(p.startswith("--") for p in parts[1:]))
            do_imports = "--imports" in parts or (not any(p.startswith("--") for p in parts[1:]))

            # Extract file path (first non-flag token)
            file_path = next((p for p in parts if not p.startswith("--")), "")
            if not file_path:
                return (
                    "**Usage:** `/fix <file> [--lint] [--imports] [--preview]`\n\n"
                    "- `--lint` — run ruff auto-fix\n"
                    "- `--imports` — sort imports with isort\n"
                    "- `--preview` — show diff without applying\n\n"
                    "If no flags given, both lint and imports are run."
                )

            fixer = AutoFixer()
            results = []

            if do_lint:
                r = await fixer.fix_lint(file_path, preview=preview)
                results.append(r)

            if do_imports:
                r = await fixer.fix_imports(file_path, preview=preview)
                results.append(r)

            if not results:
                return "No fix operations performed."

            lines = [f"**Auto-fix results for `{file_path}`:**\n"]
            for r in results:
                icon = "✓" if r.changes_made else "−"
                action = "would change" if preview else "changed"
                lines.append(f"  {icon} **{r.tool}** — {action} {r.lines_changed} line(s)")
                if preview and r.diff:
                    lines.append(f"```diff\n{r.diff[:800]}\n```")
            return "\n".join(lines)

        self.register(SlashCommand("fix", "Auto-fix lint and import issues", fix_handler))

        # Task 413: /suggest
        self._suggestions_enabled: bool = False  # type: ignore[attr-defined]

        async def suggest_handler(arg: str = "", **_: Any) -> str:
            """/suggest on|off — toggle next-action suggestions after agent responses."""
            raw = (arg or "").strip()
            if raw in ("on", "off"):
                registry._suggestions_enabled = raw == "on"
                if registry._session:
                    registry._session.config.agents.suggestions_enabled = registry._suggestions_enabled
                state = "enabled" if registry._suggestions_enabled else "disabled"
                return f"Next-action suggestions {state}."
            state = "enabled" if registry._suggestions_enabled else "disabled"
            return f"Suggestions are **{state}**. Use `/suggest on|off` to toggle."

        self.register(SlashCommand("suggest", "Toggle next-action suggestions after responses", suggest_handler))

        # Task 414: /secscan
        async def secscan_handler(arg: str = "", **_: Any) -> str:
            """/secscan [file|all] — scan for security issues."""
            from lidco.proactive.security_scanner import SecurityScanner
            import glob as _glob

            raw = (arg or "").strip()
            scanner = SecurityScanner()

            if not raw or raw == "all":
                # Scan all Python files in src/
                pattern = "src/**/*.py"
                files = _glob.glob(pattern, recursive=True)
                if not files:
                    return "No Python files found to scan."
                all_issues = []
                for f in files[:50]:  # cap to avoid huge output
                    all_issues.extend(scanner.scan_file(f))
                if not all_issues:
                    return f"No security issues found in {len(files)} file(s)."
                lines = [f"**Security scan** — {len(all_issues)} issue(s) in {len(files)} file(s)\n"]
                for issue in all_issues[:20]:
                    sev_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(issue.severity, "•")
                    lines.append(f"  {sev_icon} `{issue.file}:{issue.line}` [{issue.rule_id}] {issue.message}")
                if len(all_issues) > 20:
                    lines.append(f"\n  ... and {len(all_issues) - 20} more issues.")
                return "\n".join(lines)

            # Specific file
            issues = scanner.scan_file(raw)
            if not issues:
                return f"No security issues found in `{raw}`."
            lines = [f"**Security scan of `{raw}`** — {len(issues)} issue(s)\n"]
            for issue in issues:
                sev_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(issue.severity, "•")
                lines.append(
                    f"  {sev_icon} Line {issue.line} [{issue.rule_id}] **{issue.severity.upper()}** — {issue.message}"
                )
                if issue.snippet:
                    lines.append(f"    `{issue.snippet}`")
            return "\n".join(lines)

        self.register(SlashCommand("secscan", "Scan for security issues (hardcoded secrets, SQL injection, eval)", secscan_handler))

        # Task 415: /perf
        async def perf_handler(arg: str = "", **_: Any) -> str:
            """/perf [file] — show performance hints for a file."""
            from lidco.proactive.perf_hints import PerformanceAnalyzer

            file_path = (arg or "").strip()
            if not file_path:
                return (
                    "**Usage:** `/perf <file>`\n\n"
                    "Analyze a Python file for performance anti-patterns:\n"
                    "- String concatenation in loops\n"
                    "- `len(x) == 0` instead of `not x`\n"
                    "- `sorted()` called multiple times\n"
                    "- `list.append()` in loops (use comprehensions)\n"
                    "- Nested loops with list subscript access"
                )

            analyzer = PerformanceAnalyzer()
            hints = analyzer.analyze_file(file_path)

            if not hints:
                return f"No performance issues found in `{file_path}`."

            lines = [f"**Performance hints for `{file_path}`** — {len(hints)} hint(s)\n"]
            for h in hints:
                lines.append(f"  ⚡ Line {h.line} `{h.kind}` — {h.message}")
                lines.append(f"    💡 {h.suggestion}")
            return "\n".join(lines)

        self.register(SlashCommand("perf-hints", "Show AST-based performance hints for a Python file", perf_handler))

        # Task 416: /refactor suggest|apply
        async def refactor_suggest_apply_handler(arg: str = "", **_: Any) -> str:
            """/refactor suggest [file] | apply N — code smell refactoring."""
            from lidco.proactive.smell_refactor import SmellRefactorer

            parts = (arg or "").strip().split(None, 1)
            if not parts:
                return (
                    "**Usage:**\n"
                    "- `/refactor suggest [file]` — list code smells with refactoring preview\n"
                    "- `/refactor apply N` — apply suggestion N"
                )

            sub = parts[0]
            rest = parts[1].strip() if len(parts) > 1 else ""

            session = registry._session
            refactorer = SmellRefactorer(session=session)

            if sub == "suggest":
                file_path = rest
                if not file_path:
                    return "**Usage:** `/refactor suggest <file>`"

                suggestions = await refactorer.suggest_refactors(file_path)
                if not suggestions:
                    candidates = refactorer.find_smells(file_path)
                    if not candidates:
                        return f"No code smells found in `{file_path}`."
                    lines = [f"**Code smells in `{file_path}`** (LLM session not available for suggestions)\n"]
                    for i, c in enumerate(candidates, 1):
                        lines.append(f"  {i}. Line {c.line} `{c.kind.value}` in `{c.name}` — {c.detail}")
                    return "\n".join(lines)

                # Store suggestions for /refactor apply N
                registry._last_refactor_suggestions = suggestions  # type: ignore[attr-defined]
                lines = [f"**Refactoring suggestions for `{file_path}`** ({len(suggestions)} smell(s))\n"]
                for i, s in enumerate(suggestions, 1):
                    lines.append(f"**{i}.** Line {s.candidate.line} `{s.candidate.kind.value}` — {s.candidate.detail}")
                    if s.explanation:
                        lines.append(f"   _{s.explanation}_")
                    if s.before_snippet:
                        lines.append(f"   **Before:**\n```python\n{s.before_snippet[:300]}\n```")
                    if s.after_snippet:
                        lines.append(f"   **After:**\n```python\n{s.after_snippet[:300]}\n```")
                    lines.append("")
                lines.append("Use `/refactor apply N` to apply a suggestion.")
                return "\n".join(lines)

            if sub == "apply":
                suggestions = getattr(registry, "_last_refactor_suggestions", [])
                if not suggestions:
                    return "No suggestions available. Run `/refactor suggest <file>` first."
                try:
                    n = int(rest) - 1
                except (ValueError, TypeError):
                    return "**Usage:** `/refactor apply N` — where N is the suggestion number."
                if n < 0 or n >= len(suggestions):
                    return f"Suggestion {n+1} out of range (1–{len(suggestions)})."
                suggestion = suggestions[n]
                file_path = suggestion.candidate.file
                applied = refactorer.apply_suggestion(file_path, suggestion)
                if applied:
                    return f"✓ Applied suggestion {n+1} to `{file_path}`."
                return f"Could not apply suggestion {n+1} — snippet may have changed."

            return (
                "**Usage:**\n"
                "- `/refactor suggest [file]` — list code smells with refactoring preview\n"
                "- `/refactor apply N` — apply suggestion N"
            )

        self.register(SlashCommand("refactor-suggest", "Code smell detection and LLM-assisted refactoring", refactor_suggest_apply_handler))

