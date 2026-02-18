"""Rich-based output rendering for the CLI."""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text


class Renderer:
    """Renders formatted output to the terminal."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def markdown(self, text: str) -> None:
        """Render markdown text."""
        self.console.print(Markdown(text))

    def code(self, code: str, language: str = "python") -> None:
        """Render syntax-highlighted code."""
        syntax = Syntax(code, language, theme="monokai", line_numbers=True)
        self.console.print(syntax)

    def tool_call(self, tool_name: str, params: dict) -> None:
        """Display a tool call."""
        param_lines = [f"  {k}: {v}" for k, v in params.items()]
        content = "\n".join(param_lines)
        panel = Panel(
            content,
            title=f"Tool: {tool_name}",
            border_style="blue",
            expand=False,
        )
        self.console.print(panel)

    def tool_result(self, result: str, success: bool = True) -> None:
        """Display a tool result."""
        style = "green" if success else "red"
        # Truncate long results for display
        display = result[:2000] + "..." if len(result) > 2000 else result
        self.console.print(Panel(display, border_style=style, expand=False))

    def error(self, message: str) -> None:
        """Display an error message."""
        self.console.print(Text(f"Error: {message}", style="bold red"))

    def info(self, message: str) -> None:
        """Display an info message."""
        self.console.print(Text(message, style="dim"))

    def success(self, message: str) -> None:
        """Display a success message."""
        self.console.print(Text(message, style="bold green"))

    def warning(self, message: str) -> None:
        """Display a warning."""
        self.console.print(Text(f"Warning: {message}", style="yellow"))

    def user_prompt(self) -> None:
        """Print the user prompt indicator."""
        self.console.print(Text("\nYou: ", style="bold cyan"), end="")

    def assistant_header(self, agent: str = "lidco") -> None:
        """Styled turn header with agent name and horizontal rule."""
        label = Text()
        label.append(f"[{agent}]", style="bold magenta")
        self.console.print()
        try:
            self.console.rule(label, style="dim magenta")
        except UnicodeEncodeError:
            self.console.print(f"--- [{agent}] ---", style="bold magenta")

    def session_status(
        self,
        model: str,
        agent: str,
        turns: int,
        tokens: int,
        cost_usd: float,
    ) -> None:
        """Print a one-line session status bar before the prompt."""
        tokens_str = f"{tokens / 1000:.1f}k" if tokens >= 1000 else str(tokens)
        cost_str = f"${cost_usd:.4f}" if cost_usd else ""
        session_part = f"{tokens_str} tok"
        if cost_str:
            session_part += f" · {cost_str}"
        status = Text()
        status.append(f" {model}", style="cyan")
        status.append("  |  agent: ", style="dim")
        status.append(agent, style="green")
        status.append("  |  turn: ", style="dim")
        status.append(str(turns), style="yellow")
        status.append("  |  session: ", style="dim")
        status.append(session_part, style="blue")
        status.append(" ", style="dim")
        try:
            self.console.rule(status, style="dim")
        except UnicodeEncodeError:
            self.console.print(str(status), style="dim")

    # Tools that only read data — excluded from the summary panel.
    _READ_ONLY_TOOLS = frozenset(("file_read", "glob", "grep"))

    def summary(self, tool_calls: list[dict]) -> None:
        """Render a deduplicated summary panel of actions that changed something.

        Read-only tools (file_read, glob, grep) are excluded — the summary
        should only reflect mutations the agent performed.
        """
        seen: set[str] = set()
        lines: list[str] = []

        for tc in tool_calls:
            name = tc["tool"]
            if name in self._READ_ONLY_TOOLS:
                continue

            args = tc["args"]
            if name == "file_write":
                entry = f"  Created: {args.get('path', '?')}"
            elif name == "file_edit":
                entry = f"  Edited: {args.get('path', '?')}"
            elif name == "bash":
                cmd = str(args.get("command", "?"))[:60]
                entry = f"  Ran: {cmd}"
            elif name == "git":
                entry = f"  Git: {args.get('subcommand', '?')}"
            else:
                entry = f"  {name}"

            if entry not in seen:
                seen.add(entry)
                lines.append(entry)

        if lines:
            content = "\n".join(lines)
            panel = Panel(content, title="Summary", border_style="cyan", expand=False)
            self.console.print(panel)

    def divider(self) -> None:
        """Print a horizontal divider."""
        try:
            self.console.rule(style="dim")
        except UnicodeEncodeError:
            self.console.print("-" * 60, style="dim")
