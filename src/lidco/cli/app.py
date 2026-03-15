"""Main CLI application - REPL loop."""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lidco.__main__ import CLIFlags

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from pathlib import Path

from lidco.cli.commands import CommandRegistry
from lidco.cli.completer import LidcoCompleter
from lidco.cli.permissions import PermissionManager
from lidco.cli.renderer import Renderer
from lidco.cli.stream_display import StreamDisplay
from lidco.cli.thinking import ThinkingTimer
from lidco.core.session import Session

logger = logging.getLogger(__name__)


BANNER = """[bold magenta] LIDCO [/bold magenta][dim]- LLM-Integrated Development COmpanion v0.1.0[/dim]
[dim]Type /help for commands, /exit to quit[/dim]
"""


def _get_git_branch() -> str:
    """Return the current git branch name, or '' if unavailable."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=2,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def _levenshtein(a: str, b: str) -> int:
    """Return edit distance between two strings."""
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = curr
    return prev[-1]


def _find_similar_command(typed: str, commands: list) -> str | None:
    """Return the closest command name within edit distance 2, or None."""
    best_name, best_dist = "", 3  # max distance threshold
    for cmd in commands:
        d = _levenshtein(typed, cmd.name)
        if d < best_dist:
            best_name, best_dist = cmd.name, d
    return best_name or None


def _run_shortcut(event: Any, command: str, require_empty: bool = True) -> None:
    """Fill the prompt buffer with *command* and submit it.

    Used by keyboard shortcut handlers to trigger slash commands without
    the user having to type them.

    Args:
        event: prompt_toolkit key event.
        command: slash command to inject, e.g. ``"/clear"``.
        require_empty: when ``True`` the shortcut only fires if the buffer
            is currently empty, so editing keys (Ctrl+E = end-of-line,
            Ctrl+P = previous history line) still work while the user types.
            ``False`` fires unconditionally (e.g. Ctrl+L always clears).
    """
    buf = event.current_buffer
    if require_empty and buf.text.strip():
        return  # buffer has content — let default key handling proceed
    buf.reset()
    buf.insert_text(command)
    buf.validate_and_handle()


def _show_session_summary(
    console: Console,
    turns: int,
    tokens: int,
    cost_usd: float,
    tool_calls: int,
    files_edited: set[str],
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """Render a compact session summary panel to the console."""
    if turns == 0:
        return

    from rich.panel import Panel

    def _fmt_k(n: int) -> str:
        return f"{n / 1000:.1f}k" if n >= 1000 else str(n)

    lines: list[str] = []
    lines.append(f"Ходов:              {turns}")
    if tool_calls:
        lines.append(f"Вызовов инструм.:   {tool_calls}")
    if files_edited:
        lines.append(f"Изменено файлов:    {len(files_edited)}")
        for path in sorted(files_edited)[:5]:
            lines.append(f"  · {path}")
        if len(files_edited) > 5:
            lines.append(f"  · ... (ещё {len(files_edited) - 5})")

    if prompt_tokens or completion_tokens:
        lines.append(
            f"Токенов:            {_fmt_k(tokens)} ({_fmt_k(prompt_tokens)} вх. / {_fmt_k(completion_tokens)} исх.)"
        )
    else:
        lines.append(f"Токенов:            {_fmt_k(tokens)}")

    if cost_usd > 0:
        # Use more decimal places for very small costs so we don't show $0.0000
        cost_fmt = f"{cost_usd:.6f}".rstrip("0").rstrip(".")
        lines.append(f"Стоимость:          ~${cost_fmt}")

    console.print(Panel("\n".join(lines), title="Итоги сессии", border_style="dim"))


async def process_slash_command(
    user_input: str, commands: CommandRegistry, renderer: Renderer
) -> tuple[bool, str | None]:
    """Process a slash command.

    Returns ``(should_continue, retry_message)`` where *retry_message* is a
    non-None string when the command requests a REPL retry (``/retry``).
    """
    parts = user_input.strip().split(maxsplit=1)
    cmd_name = parts[0][1:]  # remove /
    arg = parts[1] if len(parts) > 1 else ""

    # Task 169: expand alias before lookup
    if cmd_name in commands._aliases:
        alias_target = commands._aliases[cmd_name]
        expanded = alias_target if not arg else f"{alias_target} {arg}"
        return await process_slash_command(expanded, commands, renderer)

    cmd = commands.get(cmd_name)
    if not cmd:
        # Task 163: "did you mean?" fuzzy suggestion
        _suggestion = _find_similar_command(cmd_name, commands.list_commands())
        if _suggestion:
            renderer.error(
                f"Неизвестная команда: /{cmd_name}. "
                f"Возможно, вы имели в виду: /{_suggestion}"
            )
        else:
            renderer.error(f"Неизвестная команда: /{cmd_name}. Введите /help для списка команд.")
        return True, None

    result = await cmd.handler(arg=arg)

    if result == "__EXIT__":
        renderer.info("Goodbye!")
        return False, None
    if result == "__CLEAR__":
        renderer.info("Conversation cleared.")
        return True, None
    if isinstance(result, str) and result.startswith("__RETRY__:"):
        retry_msg = result[len("__RETRY__:"):]
        renderer.info(f"Retrying: {retry_msg[:80]}")
        return True, retry_msg

    renderer.markdown(result)
    return True, None


async def run_repl(flags: "CLIFlags | None" = None) -> None:
    """Main REPL loop."""
    import io
    import os

    if sys.platform == "win32":
        os.system("")  # enable ANSI escape codes on Windows
        # Force UTF-8 output to avoid cp1251 encoding errors with Rich
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    console = Console(force_terminal=True)
    renderer = Renderer(console)

    # Initialize session (wires LLM + Tools + Agents)
    lidco_session = Session()
    config = lidco_session.config

    # Configure logging based on config
    from lidco.core.logging import setup_logging
    setup_logging(
        format=config.logging.format,
        level=config.logging.level,
        log_file=config.logging.log_file,
    )

    # Apply CLI flag overrides (highest precedence, runtime-only)
    if flags is not None:
        if flags.no_review:
            config.agents.auto_review = False
        if flags.no_plan:
            config.agents.auto_plan = False
        if flags.no_streaming:
            config.llm.streaming = False
        if flags.model:
            config.llm.default_model = flags.model
        if flags.timeout is not None:
            config.agents.agent_timeout = flags.timeout
        # Task 380: --from-pr — inject PR context on startup
        if getattr(flags, "from_pr", None) is not None:
            import subprocess as _sproc
            try:
                _pr_result = _sproc.run(
                    ["gh", "pr", "view", str(flags.from_pr), "--json",
                     "title,body,files,number,state,author"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                )
                if _pr_result.returncode == 0 and _pr_result.stdout.strip():
                    import json as _json
                    _pr_data = _json.loads(_pr_result.stdout)
                    _pr_ctx_parts = [f"## PR #{_pr_data.get('number', flags.from_pr)}: {_pr_data.get('title', '')}"]
                    if _pr_data.get("author"):
                        _pr_ctx_parts.append(f"Author: {_pr_data['author'].get('login', '')}")
                    _pr_ctx_parts.append(f"State: {_pr_data.get('state', '')}")
                    if _pr_data.get("body"):
                        _pr_ctx_parts.append(f"\n{_pr_data['body'][:1000]}")
                    if _pr_data.get("files"):
                        _files_list = [f.get("path", "") for f in _pr_data["files"][:20]]
                        _pr_ctx_parts.append("\nChanged files:\n" + "\n".join(f"- {f}" for f in _files_list))
                    lidco_session.active_pr_context = "\n".join(_pr_ctx_parts)
            except Exception:
                pass  # Non-fatal — proceed without PR context
    commands = CommandRegistry()
    commands.set_session(lidco_session)
    permissions = PermissionManager(config.permissions, console)
    active_live: list[Live | None] = [None]  # mutable container for closure

    def permission_check(tool_name: str, params: dict) -> bool:
        live = active_live[0]
        if live is not None:
            live.stop()
        try:
            return permissions.check(tool_name, params)
        finally:
            if live is not None:
                live.start()

    def continue_check(iteration: int, max_iter: int) -> bool:
        live = active_live[0]
        if live is not None:
            live.stop()
        try:
            console.print(
                f"\n[yellow]Reached {iteration} iterations (limit: {max_iter}).[/yellow]"
            )
            from rich.prompt import Confirm
            return Confirm.ask("Continue working?", default=True)
        finally:
            if live is not None:
                live.start()

    def clarification_handler(question: str, options: list[str], context: str) -> str:
        """Handle clarification questions from agents by prompting the user."""
        live = active_live[0]
        if live is not None:
            live.stop()
        try:
            from rich.panel import Panel
            from rich.prompt import IntPrompt, Prompt

            panel_content = f"[bold]{question}[/bold]"
            if context:
                panel_content += f"\n[dim]{context}[/dim]"

            if options:
                for i, opt in enumerate(options, 1):
                    panel_content += f"\n  [cyan]{i}.[/cyan] {opt}"

            console.print(Panel(panel_content, title="Clarification", border_style="yellow"))

            if options:
                choice = IntPrompt.ask(
                    "Your choice",
                    choices=[str(i) for i in range(1, len(options) + 1)],
                    default=1,
                )
                return options[choice - 1]
            else:
                return Prompt.ask("Your answer")
        finally:
            if live is not None:
                live.start()

    lidco_session.orchestrator.set_permission_handler(permission_check)
    lidco_session.orchestrator.set_continue_handler(continue_check)
    lidco_session.orchestrator.set_clarification_handler(clarification_handler)

    def plan_editor(plan_text: str) -> str | None:
        """Show the interactive plan editor and return the filtered plan (or None to reject)."""
        live = active_live[0]
        if live is not None:
            live.stop()
        try:
            from lidco.cli.plan_editor import edit_plan_interactively
            return edit_plan_interactively(plan_text, console)
        finally:
            if live is not None:
                live.start()

    lidco_session.orchestrator.set_plan_editor(plan_editor)

    # Task 137: agent selection announcement
    def on_agent_selected(agent_name: str, auto: bool) -> None:
        if auto:
            renderer.agent_selected(agent_name)

    lidco_session.orchestrator.set_agent_selected_callback(on_agent_selected)

    # Task 140: model fallback notification
    def on_model_fallback(failed: str, fallback: str, reason: str) -> None:
        renderer.model_fallback(failed, fallback, reason)

    lidco_session.llm.set_fallback_callback(on_model_fallback)

    # Task 283: wire CheckpointManager for /checkpoint undo
    from lidco.cli.checkpoint import CheckpointManager
    _checkpoint_mgr = CheckpointManager()
    commands._checkpoint_mgr = _checkpoint_mgr

    # Task 285: wire SessionStore
    from lidco.cli.session_store import SessionStore
    commands._session_store = SessionStore()

    # Task 383: --session <name> — load named session on startup
    if flags is not None and getattr(flags, "session_name", None):
        _sname = flags.session_name
        _sdata = commands._session_store.find_by_name(_sname)
        if _sdata is not None:
            _sorch = getattr(lidco_session, "orchestrator", None)
            if _sorch is not None:
                _sorch._conversation_history = _sdata.get("history", [])
            commands._current_session_id = _sdata.get("session_id")
            logger.info("Loaded named session '%s' (%s)", _sname, commands._current_session_id)

    # Task 385: --profile <name> — apply workspace profile on startup
    if flags is not None and getattr(flags, "profile_name", None):
        try:
            from lidco.core.profiles import ProfileLoader
            _ploader = ProfileLoader()
            _pdata = _ploader.load(flags.profile_name, Path.cwd())
            if _pdata is not None:
                if "agents" in _pdata and isinstance(_pdata["agents"], dict):
                    for _k, _v in _pdata["agents"].items():
                        if hasattr(config.agents, _k):
                            try:
                                setattr(config.agents, _k, _v)
                            except Exception:
                                pass
                if "llm" in _pdata and isinstance(_pdata["llm"], dict):
                    for _k, _v in _pdata["llm"].items():
                        if hasattr(config.llm, _k):
                            try:
                                setattr(config.llm, _k, _v)
                            except Exception:
                                pass
                commands._active_profile = flags.profile_name
        except Exception:
            pass  # Profile loading is non-fatal

    # Task 153: overwrite confirmation for file_write tool
    from lidco.tools.file_write import FileWriteTool
    _fw_tool = lidco_session.tool_registry.get("file_write")
    if isinstance(_fw_tool, FileWriteTool):
        _fw_tool.set_checkpoint_callback(_checkpoint_mgr.record)
    if isinstance(_fw_tool, FileWriteTool):
        async def _confirm_overwrite(path: str, old: str, new: str) -> bool:
            live = active_live[0]
            if live is not None:
                try:
                    live.stop()
                except Exception:
                    pass
                active_live[0] = None
            diff = FileWriteTool.build_diff(old, new, path)
            console.print()
            if diff:
                from rich.syntax import Syntax
                from rich.panel import Panel
                console.print(Panel(
                    Syntax(diff, "diff", theme="monokai"),
                    title=f"Перезапись: {path}",
                    border_style="yellow",
                    expand=False,
                ))
            else:
                console.print(f"  [yellow]Файл не изменился:[/yellow] {path}")
            try:
                answer = await asyncio.to_thread(
                    input, "  Перезаписать? [д/N] "
                )
            except (EOFError, KeyboardInterrupt):
                answer = ""
            return answer.strip().lower() in ("y", "yes", "д", "да")

        _fw_tool.set_confirm_callback(_confirm_overwrite)

    # Resolve default agent from flag (validated against registry)
    default_agent: str | None = None
    if flags is not None and flags.agent:
        available = lidco_session.agent_registry.list_names()
        if flags.agent not in available:
            renderer.error(
                f"Unknown agent: '{flags.agent}'. Available: {', '.join(available)}"
            )
            return
        default_agent = flags.agent

    console.print(BANNER)

    # Task 162: startup project card
    from rich.panel import Panel
    from rich.text import Text as RichText
    _cwd = Path.cwd()
    _proj_name = _cwd.name
    _branch_startup = _get_git_branch()
    agents = lidco_session.agent_registry.list_names()
    _card_lines: list[str] = []
    _card_lines.append(f"[bold cyan]Проект:[/bold cyan]  {_proj_name}  [dim]{_cwd}[/dim]")
    if _branch_startup:
        _card_lines.append(f"[bold blue]Ветка:[/bold blue]    {_branch_startup}")
    _card_lines.append(f"[bold green]Модель:[/bold green]   {config.llm.default_model}")
    _card_lines.append(f"[bold magenta]Агенты:[/bold magenta]   {', '.join(agents)}")
    if default_agent:
        _card_lines.append(f"[bold yellow]По умолчанию:[/bold yellow] {default_agent}")
    if not config.agents.auto_review:
        _card_lines.append("[dim]Auto-review: выключен[/dim]")
    if not config.agents.auto_plan:
        _card_lines.append("[dim]Auto-plan: выключен[/dim]")
    _card_lines.append("[dim]/help — команды  ·  /shortcuts — горячие клавиши[/dim]")
    console.print(Panel("\n".join(_card_lines), border_style="dim", expand=False))
    renderer.divider()

    # Check for LIDCO.md and offer to create it
    from lidco.core.rules import RulesManager

    rules_mgr = RulesManager()
    if not rules_mgr.has_rules_file():
        from rich.prompt import Confirm

        console.print(
            "\n[yellow]No LIDCO.md found in this project.[/yellow]\n"
            "[dim]LIDCO.md stores project rules and conventions that guide the assistant.[/dim]"
        )
        try:
            should_create = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: Confirm.ask("Create LIDCO.md with default rules?", default=True),
            )
            if should_create:
                path = rules_mgr.init_rules()
                renderer.info(f"Created {path}")
                renderer.info("Edit it anytime or use /rules add to append rules.")
            else:
                renderer.info("Skipped. You can run /init later to create it.")
        except (KeyboardInterrupt, EOFError):
            renderer.info("Skipped.")
        console.print()

    # Setup prompt with history, completion, and multiline
    history_dir = Path.home() / ".lidco"
    history_dir.mkdir(parents=True, exist_ok=True)

    command_meta = {cmd.name: cmd.description for cmd in commands.list_commands()}
    completer = LidcoCompleter(
        command_meta=command_meta,
        agent_names=lidco_session.agent_registry.list_names(),
    )

    # Task 151: shortcut registry — also used by /shortcuts command.
    # Each entry: (display_key, command, description)
    SHORTCUTS: list[tuple[str, str, str]] = [
        ("Ctrl+L",       "/clear",  "Очистить историю сессии"),
        ("Ctrl+R",       "/retry",  "Повторить последний запрос"),
        ("Ctrl+E",       "/export", "Экспортировать сессию"),
        ("Ctrl+P",       "/status", "Показать статус сессии"),
        ("Enter",        "",        "Отправить сообщение"),
        ("Esc+Enter",    "",        "Новая строка в сообщении"),
    ]

    # Key bindings: Enter submits, Shift+Enter adds newline (like Telegram/Slack).
    kb = KeyBindings()

    @kb.add("enter")
    def _submit(event: Any) -> None:
        """Enter submits the input."""
        event.current_buffer.validate_and_handle()

    @kb.add("escape", "enter")
    def _newline(event: Any) -> None:
        """Alt/Meta+Enter (or Escape then Enter) inserts a newline."""
        event.current_buffer.insert_text("\n")

    @kb.add("c-j")
    def _also_submit(event: Any) -> None:
        """Ctrl+J also submits (convenient alternative)."""
        event.current_buffer.validate_and_handle()

    @kb.add("c-l")
    def _shortcut_clear(event: Any) -> None:
        """Ctrl+L → /clear (always, even with text in buffer)."""
        _run_shortcut(event, "/clear", require_empty=False)

    @kb.add("c-r")
    def _shortcut_retry(event: Any) -> None:
        """Ctrl+R → /retry (only when buffer is empty)."""
        _run_shortcut(event, "/retry")

    @kb.add("c-e")
    def _shortcut_export(event: Any) -> None:
        """Ctrl+E → /export (only when buffer is empty)."""
        _run_shortcut(event, "/export")

    @kb.add("c-p")
    def _shortcut_status(event: Any) -> None:
        """Ctrl+P → /status (only when buffer is empty)."""
        _run_shortcut(event, "/status")

    @kb.add("escape", "e")
    def _shortcut_editor(event: Any) -> None:
        """Q55/368 — Alt+E (Escape then E) opens $EDITOR for the current buffer."""
        import os
        import subprocess
        import tempfile
        editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "notepad" if sys.platform == "win32" else "nano"))
        buf = event.current_buffer
        current_text = buf.text
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".md", prefix="lidco_", encoding="utf-8", delete=False
            ) as f:
                f.write(current_text)
                tmp_path = f.name
            subprocess.run([editor, tmp_path], check=False)
            with open(tmp_path, encoding="utf-8") as f:
                new_text = f.read()
            os.unlink(tmp_path)
            buf.set_document(
                buf.document.__class__(text=new_text, cursor_position=len(new_text)),
                bypass_readonly=True,
            )
        except Exception:
            pass  # Fail silently — user stays in current buffer

    prompt_session: PromptSession[str] = PromptSession(
        history=FileHistory(str(history_dir / "history")),
        completer=completer,
        key_bindings=kb,
        multiline=True,
    )

    # Task 158: git branch shown in status bar
    _git_branch: str = _get_git_branch()

    # Session-level cumulative statistics
    session_tokens: int = 0
    session_prompt_tokens: int = 0
    session_completion_tokens: int = 0
    session_cost_usd: float = 0.0
    session_turns: int = 0
    session_tool_calls: int = 0
    session_files_edited: set[str] = set()
    current_agent: str = default_agent or "auto"

    # Task 150: smart hint — shown only first _MAX_HINT_SHOWS times, then hidden
    from lidco.core.prefs import PrefsStore
    _prefs = PrefsStore()
    # Mutable state shared between get_prompt() and the loop
    _prompt_state: dict = {"show_hint": _prefs.should_show_newline_hint()}

    # Task 142: multiline line counter in prompt
    def get_prompt() -> HTML:
        try:
            buf = prompt_session.app.current_buffer
            raw = buf.text
            line_count = (raw.count("\n") + 1) if isinstance(raw, str) and raw else 1
        except Exception:
            line_count = 1
        if line_count > 1:
            return HTML(
                f"<ansigreen><b>[You]</b></ansigreen> "
                f"<ansiyellow>[{line_count} строк]</ansiyellow> "
                f"<ansiwhite>\u203a</ansiwhite> "
            )
        if _prompt_state["show_hint"]:
            return HTML(
                "<ansigreen><b>[You]</b></ansigreen> "
                "<ansigray>(Esc+Enter для новой строки)</ansigray> "
                "<ansiwhite>\u203a</ansiwhite> "
            )
        return HTML("<ansigreen><b>[You]</b></ansigreen> <ansiwhite>\u203a</ansiwhite> ")

    while True:
        try:
            # Task 152: reflect /lock changes in the status bar each turn
            current_agent = commands.locked_agent or default_agent or "auto"
            renderer.session_status(
                model=config.llm.default_model,
                agent=current_agent,
                turns=session_turns,
                tokens=session_tokens,
                cost_usd=session_cost_usd,
                branch=_git_branch,
            )

            # Task 138: context window warning at 80%
            try:
                _budget_limit = int(lidco_session.token_budget.session_limit or 0)
                _ctx_limit = _budget_limit if _budget_limit > 0 else int(config.agents.context_window)
                if _ctx_limit > 0 and session_tokens > 0:
                    _ctx_pct = int(session_tokens / _ctx_limit * 100)
                    if _ctx_pct >= 80:
                        renderer.context_warning(_ctx_pct)
            except (TypeError, ValueError, AttributeError):
                pass

            user_input = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: prompt_session.prompt(get_prompt()),
            )

            # Task 150: record hint shown and update for next iteration
            if _prompt_state["show_hint"]:
                _prefs.record_newline_hint_shown()
                _prompt_state["show_hint"] = _prefs.should_show_newline_hint()

            if not user_input.strip():
                continue

            # Handle slash commands
            if user_input.strip().startswith("/"):
                should_continue, retry_msg = await process_slash_command(user_input, commands, renderer)
                if not should_continue:
                    break
                if retry_msg:
                    # /retry — feed the message back as if the user typed it
                    user_input = retry_msg
                else:
                    continue

            # Check for @agent syntax: "@reviewer review this code"
            forced_agent: str | None = None
            message = user_input.strip()

            # Task 282: @-mentions — expand @path/to/file in message
            import re as _re_at
            _AT_FILE_RE = _re_at.compile(r"@([^\s@]+\.[a-zA-Z0-9]+)")
            _at_matches = _AT_FILE_RE.findall(message)
            _at_injected: list[str] = []
            for _at_path in _at_matches:
                try:
                    _at_p = Path(_at_path)
                    if _at_p.is_file():
                        _at_content = _at_p.read_text(encoding="utf-8", errors="replace")[:4000]
                        _at_injected.append(f"## @{_at_path}\n\n```\n{_at_content}\n```")
                        message = message.replace(f"@{_at_path}", f"`{_at_path}`", 1)
                except OSError:
                    pass
            # Task 278: /mention — inject pre-mentioned files
            for _mf in getattr(commands, "_mentions", []):
                try:
                    _mf_p = Path(_mf)
                    if _mf_p.is_file():
                        _mf_content = _mf_p.read_text(encoding="utf-8", errors="replace")[:4000]
                        _at_injected.append(f"## Mentioned: {_mf}\n\n```\n{_mf_content}\n```")
                except OSError:
                    pass
            if hasattr(commands, "_mentions"):
                commands._mentions = []  # clear after use

            # Task 174: /vars — substitute {{VAR}} in user message
            if commands._vars and "{{" in message:
                import re as _re
                def _substitute_var(m: "_re.Match[str]") -> str:
                    return commands._vars.get(m.group(1), m.group(0))
                message = _re.sub(r"\{\{([A-Z0-9_]+)\}\}", _substitute_var, message)

            # Track last message for /retry
            if not message.startswith("/"):
                commands.last_message = message
            if message.startswith("@"):
                parts = message.split(maxsplit=1)
                forced_agent = parts[0][1:]
                message = parts[1] if len(parts) > 1 else ""
                if not message:
                    renderer.error(f"Usage: @{forced_agent} <message>")
                    continue
            elif commands.locked_agent:
                # Task 152: /lock <agent> pins agent for the whole session
                forced_agent = commands.locked_agent
            elif default_agent:
                forced_agent = default_agent

            # Check token budget before routing to agent
            from lidco.core.token_budget import TokenBudgetExceeded
            try:
                lidco_session.token_budget.check_remaining()
            except TokenBudgetExceeded as exc:
                renderer.error(str(exc))
                continue

            # Route to agent orchestrator
            renderer.assistant_header(agent=forced_agent or "lidco", turn=session_turns + 1)
            console.print()

            try:
                context = lidco_session.get_full_context()
                # Task 173: inject pinned notes if any
                if commands._pins:
                    _pins_block = "\n\n".join(
                        f"[{i}] {pin}" for i, pin in enumerate(commands._pins, 1)
                    )
                    _pins_section = f"## Pinned Notes\n\n{_pins_block}"
                    context = f"{_pins_section}\n\n{context}" if context else _pins_section
                # Task 167: inject session note if set
                if commands.session_note:
                    context = f"## Session Note\n\n{commands.session_note}\n\n{context}" if context else f"## Session Note\n\n{commands.session_note}"
                # Task 282/278: inject @-mention and /mention file contents
                if _at_injected:
                    _at_block = "\n\n".join(_at_injected)
                    context = f"{_at_block}\n\n{context}" if context else _at_block

                # Task 272: inject /add-dir directories as context hint
                if getattr(commands, "_extra_dirs", []):
                    _extra = "\n".join(f"  · {d}" for d in commands._extra_dirs)
                    _dir_section = f"## Extra Directories In Scope\n\n{_extra}"
                    context = f"{_dir_section}\n\n{context}" if context else _dir_section

                # Task 172: inject focus file content if set
                if commands.focus_file:
                    try:
                        _focus_content = Path(commands.focus_file).read_text(encoding="utf-8", errors="replace")
                        _focus_section = f"## Focus File: {commands.focus_file}\n\n```\n{_focus_content[:4000]}\n```"
                        context = f"{_focus_section}\n\n{context}" if context else _focus_section
                    except OSError:
                        commands.focus_file = ""  # auto-clear if file gone
                use_streaming = config.llm.streaming
                _t0 = time.monotonic()

                if use_streaming:
                    # Streaming mode: persistent status bar at the bottom,
                    # reasoning text + tool events scroll above it.
                    stream_display = StreamDisplay(console)
                    stream_display.set_debug_mode(lidco_session.debug_mode)
                    active_live[0] = stream_display.live

                    def on_status_stream(status: str) -> None:
                        stream_display.on_status(status)

                    def on_tokens_stream(total: int, total_cost_usd: float = 0.0) -> None:
                        stream_display.update_tokens(total, total_cost_usd)
                        # Q55/374: update context window meter
                        _ctx_max = getattr(lidco_session.config.llm, "context_window", 128_000)
                        stream_display.update_context_usage(total, _ctx_max)

                    def on_text_chunk(text: str) -> None:
                        stream_display.on_text_chunk(text)

                    def on_tool_event(
                        event: str, tool_name: str, args: dict, result: Any = None
                    ) -> None:
                        stream_display.on_tool_event(event, tool_name, args, result)

                    def on_phase(name: str, phase_status: str) -> None:
                        stream_display.set_phase(name, phase_status)

                    orch = lidco_session.orchestrator
                    orch.set_status_callback(on_status_stream)
                    orch.set_token_callback(on_tokens_stream)
                    orch.set_stream_callback(on_text_chunk)
                    orch.set_tool_event_callback(on_tool_event)
                    orch.set_phase_callback(on_phase)

                    try:
                        response = await orch.handle(
                            message,
                            agent_name=forced_agent,
                            context=context,
                        )
                    finally:
                        orch.set_status_callback(None)
                        orch.set_token_callback(None)
                        orch.set_stream_callback(None)
                        orch.set_tool_event_callback(None)
                        orch.set_phase_callback(None)
                        stream_display.finish()
                        active_live[0] = None

                else:
                    # Non-streaming fallback: spinner with ThinkingTimer
                    timer = ThinkingTimer("Обработка")

                    def on_status(status: str) -> None:
                        timer.label = status

                    def on_tokens(total: int, total_cost_usd: float = 0.0) -> None:
                        timer.total_tokens = total

                    lidco_session.orchestrator.set_status_callback(on_status)
                    lidco_session.orchestrator.set_token_callback(on_tokens)

                    try:
                        live = Live(timer, console=console, refresh_per_second=4, transient=True)
                        active_live[0] = live
                        with live:
                            response = await lidco_session.orchestrator.handle(
                                message,
                                agent_name=forced_agent,
                                context=context,
                            )
                    finally:
                        active_live[0] = None
                        lidco_session.orchestrator.set_status_callback(None)
                        lidco_session.orchestrator.set_token_callback(None)

                    # Show tool calls if configured (non-streaming only)
                    if config.cli.show_tool_calls and response.tool_calls_made:
                        for tc in response.tool_calls_made:
                            renderer.tool_call(tc["tool"], tc["args"])

                    renderer.markdown(response.content)

                # Accumulate session statistics
                _elapsed = time.monotonic() - _t0
                commands._turn_times.append(_elapsed)  # Task 175: /timing
                turn_tokens = response.token_usage.total_tokens
                turn_cost = getattr(response.token_usage, "total_cost_usd", 0.0) or 0.0
                session_tokens += turn_tokens
                session_prompt_tokens += response.token_usage.prompt_tokens
                session_completion_tokens += response.token_usage.completion_tokens
                session_cost_usd += turn_cost
                session_turns += 1
                session_tool_calls += len(response.tool_calls_made)
                for tc in response.tool_calls_made:
                    if tc.get("tool") in ("file_write", "file_edit"):
                        path = tc.get("args", {}).get("path", "")
                        if path:
                            session_files_edited.add(path)
                            commands._edited_files.append(path)  # Task 171: /recent
                current_agent = forced_agent or getattr(response, "agent_used", None) or "auto"

                # Task 182: /profile — accumulate per-agent stats
                _astats = commands._agent_stats.setdefault(current_agent, {"calls": 0, "tokens": 0, "elapsed": 0.0})
                _astats["calls"] += 1
                _astats["tokens"] += turn_tokens
                _astats["elapsed"] += _elapsed

                # Record into token budget (enables budget limit enforcement)
                lidco_session.token_budget.record(
                    tokens=turn_tokens,
                    prompt_tokens=response.token_usage.prompt_tokens,
                    completion_tokens=response.token_usage.completion_tokens,
                    cost_usd=turn_cost,
                    role=current_agent,
                )

                # Show git diff and run linting when the agent edited files
                _FILE_EDIT_TOOLS = frozenset({"file_write", "file_edit"})
                _edited_tool_calls = [
                    tc for tc in response.tool_calls_made
                    if tc.get("tool") in _FILE_EDIT_TOOLS
                ]
                if _edited_tool_calls:
                    from lidco.cli.diff_viewer import show_git_diff
                    show_git_diff(console)

                    _edited_paths = [
                        tc.get("args", {}).get("path", "")
                        for tc in _edited_tool_calls
                    ]
                    _edited_paths = list({p for p in _edited_paths if p})
                    if _edited_paths:
                        from lidco.cli.linter import show_lint_results
                        show_lint_results(console, _edited_paths)

                # Show summary and compact turn line (both modes)
                if response.tool_calls_made:
                    renderer.summary(response.tool_calls_made)

                _files_changed = len({
                    tc.get("args", {}).get("path", "")
                    for tc in response.tool_calls_made
                    if tc.get("tool") in ("file_write", "file_edit")
                    and tc.get("args", {}).get("path")
                })
                renderer.turn_summary(
                    model=response.model_used,
                    iterations=response.iterations,
                    tool_calls=len(response.tool_calls_made),
                    files_changed=_files_changed,
                    tokens=turn_tokens,
                    cost_usd=turn_cost,
                    elapsed=_elapsed,
                )

                # Task 186: /autosave — fire export every N turns
                if commands._autosave_interval > 0:
                    commands._autosave_turn_count += 1
                    if commands._autosave_turn_count % commands._autosave_interval == 0:
                        try:
                            import json as _json
                            _export_dir = Path.cwd() / ".lidco" / "autosave"
                            _export_dir.mkdir(parents=True, exist_ok=True)
                            _ts = int(time.monotonic() * 1000)
                            _export_path = _export_dir / f"session_{_ts}.json"
                            _history = getattr(lidco_session.orchestrator, "_conversation_history", [])
                            _export_path.write_text(
                                _json.dumps({"history": _history}, ensure_ascii=False, indent=2),
                                encoding="utf-8",
                            )
                            renderer.info(f"Autosaved → {_export_path.name}")
                        except Exception:
                            pass

                # Task 187: /remind — fire due reminders
                # Q54/361: use set-based removal to avoid index shifting after pop
                _current_turn = len(commands._turn_times)
                _fired_set: set[int] = set()
                for _ri, _rem in enumerate(commands._reminders):
                    if _current_turn >= _rem["fire_at"]:
                        renderer.info(f"⏰ Напоминание: {_rem['text']}")
                        _fired_set.add(_ri)
                if _fired_set:
                    commands._reminders = [
                        r for i, r in enumerate(commands._reminders)
                        if i not in _fired_set
                    ]

                # Task 155: contextual next-step suggestions
                from lidco.core.suggestions import suggest
                _hist_len = len(getattr(lidco_session.orchestrator, "_conversation_history", []))
                _hints = suggest(response.tool_calls_made, response.content, history_len=_hist_len)
                renderer.suggestions(_hints)

                # Flush console so output appears before prompt_toolkit blocks
                if hasattr(console.file, "flush"):
                    console.file.flush()

                # Auto-save to memory if enabled
                if config.memory.enabled and config.memory.auto_save:
                    if response.tool_calls_made:
                        lidco_session.memory.add(
                            key=f"action_{len(lidco_session.memory.list_all())}",
                            content=f"Q: {message[:200]} -> {len(response.tool_calls_made)} tool calls",
                            category="actions",
                            source=str(Path.cwd()),
                        )

            except Exception as e:
                logger.exception("Agent error")
                renderer.friendly_error(e)

        except KeyboardInterrupt:
            renderer.info("\nUse /exit to quit.")
            continue
        except EOFError:
            renderer.info("\nGoodbye!")
            break

    lidco_session.close()

    # Task 383: auto-save named session on exit
    if flags is not None and getattr(flags, "session_name", None):
        try:
            _exit_orch = getattr(lidco_session, "orchestrator", None)
            _exit_history = getattr(_exit_orch, "_conversation_history", []) if _exit_orch else []
            if _exit_history:
                commands._session_store.save(
                    _exit_history,
                    session_id=getattr(commands, "_current_session_id", None),
                    metadata={"name": flags.session_name},
                )
        except Exception:
            pass  # Non-fatal

    _show_session_summary(
        console,
        turns=session_turns,
        tokens=session_tokens,
        cost_usd=session_cost_usd,
        tool_calls=session_tool_calls,
        files_edited=session_files_edited,
        prompt_tokens=session_prompt_tokens,
        completion_tokens=session_completion_tokens,
    )


def run_cli(flags: "CLIFlags | None" = None) -> None:
    """Entry point for the CLI."""
    try:
        asyncio.run(run_repl(flags=flags))
    except KeyboardInterrupt:
        sys.exit(0)
