"""Main CLI application - REPL loop."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

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


BANNER = """[bold magenta] LIDCO [/bold magenta][dim]- LLM-Integrated Development COmpanion v0.1.0[/dim]
[dim]Type /help for commands, /exit to quit[/dim]
"""


async def process_slash_command(
    user_input: str, commands: CommandRegistry, renderer: Renderer
) -> bool:
    """Process a slash command. Returns True if should continue REPL, False to exit."""
    parts = user_input.strip().split(maxsplit=1)
    cmd_name = parts[0][1:]  # remove /
    arg = parts[1] if len(parts) > 1 else ""

    cmd = commands.get(cmd_name)
    if not cmd:
        renderer.error(f"Unknown command: /{cmd_name}. Type /help for available commands.")
        return True

    result = await cmd.handler(arg=arg)

    if result == "__EXIT__":
        renderer.info("Goodbye!")
        return False
    if result == "__CLEAR__":
        renderer.info("Conversation cleared.")
        return True

    renderer.markdown(result)
    return True


async def run_repl() -> None:
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

    console.print(BANNER)
    renderer.info(f"Model: {config.llm.default_model}")
    renderer.info(f"Working directory: {Path.cwd()}")
    agents = lidco_session.agent_registry.list_names()
    renderer.info(f"Agents: {', '.join(agents)}")
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

    prompt_session: PromptSession[str] = PromptSession(
        history=FileHistory(str(history_dir / "history")),
        completer=completer,
        key_bindings=kb,
        multiline=True,
    )

    # Session-level cumulative statistics
    session_tokens: int = 0
    session_cost_usd: float = 0.0
    session_turns: int = 0
    current_agent: str = "auto"

    def get_prompt() -> HTML:
        return HTML("<ansigreen><b>[You]</b></ansigreen> <ansigray>(Esc+Enter for newline)</ansigray> <ansiwhite>›</ansiwhite> ")

    while True:
        try:
            renderer.session_status(
                model=config.llm.default_model,
                agent=current_agent,
                turns=session_turns,
                tokens=session_tokens,
                cost_usd=session_cost_usd,
            )
            user_input = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: prompt_session.prompt(get_prompt()),
            )

            if not user_input.strip():
                continue

            # Handle slash commands
            if user_input.strip().startswith("/"):
                should_continue = await process_slash_command(user_input, commands, renderer)
                if not should_continue:
                    break
                continue

            # Check for @agent syntax: "@reviewer review this code"
            forced_agent: str | None = None
            message = user_input.strip()
            if message.startswith("@"):
                parts = message.split(maxsplit=1)
                forced_agent = parts[0][1:]
                message = parts[1] if len(parts) > 1 else ""
                if not message:
                    renderer.error(f"Usage: @{forced_agent} <message>")
                    continue

            # Route to agent orchestrator
            renderer.assistant_header(agent=forced_agent or "lidco")
            console.print()

            try:
                context = lidco_session.get_full_context()
                use_streaming = config.llm.streaming

                if use_streaming:
                    # Streaming mode: persistent status bar at the bottom,
                    # reasoning text + tool events scroll above it.
                    stream_display = StreamDisplay(console)
                    active_live[0] = stream_display.live

                    def on_status_stream(status: str) -> None:
                        stream_display.on_status(status)

                    def on_tokens_stream(total: int, total_cost_usd: float = 0.0) -> None:
                        stream_display.update_tokens(total, total_cost_usd)

                    def on_text_chunk(text: str) -> None:
                        stream_display.on_text_chunk(text)

                    def on_tool_event(
                        event: str, tool_name: str, args: dict, result: Any = None
                    ) -> None:
                        stream_display.on_tool_event(event, tool_name, args, result)

                    orch = lidco_session.orchestrator
                    orch.set_status_callback(on_status_stream)
                    orch.set_token_callback(on_tokens_stream)
                    orch.set_stream_callback(on_text_chunk)
                    orch.set_tool_event_callback(on_tool_event)

                    try:
                        response = await orch.handle(
                            message,
                            agent_name=forced_agent,
                            context=context,
                        )
                    finally:
                        orch.set_status_callback(None)
                        orch.set_stream_callback(None)
                        orch.set_tool_event_callback(None)
                        stream_display.finish()
                        active_live[0] = None

                else:
                    # Non-streaming fallback: spinner with ThinkingTimer
                    timer = ThinkingTimer("Thinking")

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

                    # Show tool calls if configured (non-streaming only)
                    if config.cli.show_tool_calls and response.tool_calls_made:
                        for tc in response.tool_calls_made:
                            renderer.tool_call(tc["tool"], tc["args"])

                    renderer.markdown(response.content)

                # Accumulate session statistics
                turn_tokens = response.token_usage.total_tokens
                turn_cost = getattr(response.token_usage, "total_cost_usd", 0.0) or 0.0
                session_tokens += turn_tokens
                session_cost_usd += turn_cost
                session_turns += 1
                current_agent = forced_agent or getattr(response, "agent_used", None) or "auto"

                # Show summary and token info (both modes)
                if response.tool_calls_made:
                    renderer.summary(response.tool_calls_made)

                tokens_str = f"{turn_tokens / 1000:.1f}k" if turn_tokens >= 1000 else str(turn_tokens)
                renderer.info(
                    f"[{response.model_used} | {response.iterations} iterations | {tokens_str} tokens]"
                )

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
                renderer.error(f"Agent error: {e}")

        except KeyboardInterrupt:
            renderer.info("\nUse /exit to quit.")
            continue
        except EOFError:
            renderer.info("\nGoodbye!")
            break


def run_cli() -> None:
    """Entry point for the CLI."""
    try:
        asyncio.run(run_repl())
    except KeyboardInterrupt:
        sys.exit(0)
