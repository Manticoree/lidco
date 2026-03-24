"""Rich-based output rendering for the CLI."""

from __future__ import annotations

import re

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text


class Renderer:
    """Renders formatted output to the terminal."""

    # Task 134: agent icon + color per type
    _AGENT_STYLES: dict[str, tuple[str, str]] = {
        "coder":     ("\u2328 ", "bold green"),       # ⌨
        "debugger":  ("\u25cf ", "bold red"),          # ●
        "tester":    ("\u2756 ", "bold blue"),         # ✦
        "architect": ("\u25c8 ", "bold yellow"),       # ◈
        "reviewer":  ("\u25ce ", "bold cyan"),         # ◎
        "refactor":  ("\u21ba ", "bold magenta"),      # ↺
        "security":  ("\u26a0 ", "bold red"),          # ⚠
        "profiler":  ("\u23f1 ", "bold yellow"),       # ⏱
        "explain":   ("\u2139 ", "bold cyan"),         # ℹ
        "auto":      ("\u25b6 ", "bold magenta"),      # ▶
        "lidco":     ("\u25b6 ", "bold magenta"),      # ▶
    }

    # Task 135: code fence pattern — ```lang\ncode\n```
    _CODE_FENCE_RE = re.compile(
        r"```(\w*)\n(.*?)```",
        re.DOTALL,
    )
    _CODE_PANEL_MIN_LINES = 10

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def markdown(self, text: str) -> None:
        """Render markdown, promoting large code blocks to syntax-highlighted panels."""
        if not text:
            return
        segments = self._split_code_blocks(text)
        for kind, content, lang in segments:
            if kind == "code":
                syntax = Syntax(
                    content,
                    lang or "text",
                    theme="monokai",
                    line_numbers=True,
                    word_wrap=True,
                )
                self.console.print(Panel(syntax, border_style="dim", expand=False))
            else:
                if content.strip():
                    self.console.print(Markdown(content))

    def _split_code_blocks(
        self, text: str
    ) -> list[tuple[str, str, str]]:
        """Split text into alternating prose and code segments.

        Returns list of (kind, content, lang) where kind is "prose" or "code".
        Code blocks with >= _CODE_PANEL_MIN_LINES lines become "code" kind;
        shorter ones are left in prose for Markdown rendering.
        """
        result: list[tuple[str, str, str]] = []
        last_end = 0

        for m in self._CODE_FENCE_RE.finditer(text):
            lang = m.group(1).strip()
            code = m.group(2)

            # Prose before this block
            prose = text[last_end : m.start()]
            if prose:
                result.append(("prose", prose, ""))

            if code.count("\n") + 1 >= self._CODE_PANEL_MIN_LINES:
                result.append(("code", code.rstrip("\n"), lang))
            else:
                # Small block — keep in prose with original fence
                result.append(("prose", m.group(0), ""))

            last_end = m.end()

        # Remaining prose after the last block
        tail = text[last_end:]
        if tail:
            result.append(("prose", tail, ""))

        return result or [("prose", text, "")]

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
        display = result[:2000] + "..." if len(result) > 2000 else result
        self.console.print(Panel(display, border_style=style, expand=False))

    def error(self, message: str) -> None:
        """Display an error message."""
        self.console.print(Text(f"Ошибка: {message}", style="bold red"))

    def info(self, message: str) -> None:
        """Display an info message."""
        self.console.print(Text(message, style="dim"))

    def success(self, message: str) -> None:
        """Display a success message."""
        self.console.print(Text(message, style="bold green"))

    def warning(self, message: str) -> None:
        """Display a compact warning (single line, no verbose prefix)."""
        self.console.print(Text(f"[!] {message}", style="yellow"))

    def status(self, message: str, style: str = "cyan") -> None:
        """Show current action as a clean one-liner."""
        line = Text()
        line.append("-> ", style=style)
        line.append(message)
        self.console.print(line)

    def phase_status(self, phase: str, detail: str = "") -> None:
        """Show current phase/action in a compact one-liner."""
        line = Text()
        line.append(phase, style="bold cyan")
        if detail:
            line.append(f"  {detail}", style="dim")
        self.console.print(line)

    def user_prompt(self) -> None:
        """Print the user prompt indicator."""
        self.console.print(Text("\nYou: ", style="bold cyan"), end="")

    def assistant_header(self, agent: str = "lidco", turn: int = 0) -> None:
        """Styled turn header: turn number + icon + agent name + horizontal rule."""
        style_info = self._AGENT_STYLES.get(agent.lower())
        label = Text()
        if turn > 0:
            label.append(f"Ход {turn}", style="dim")
            label.append("  ·  ", style="dim")
        if style_info:
            icon, color = style_info
            label.append(icon, style=color)
            label.append(agent, style=color)
        else:
            label.append("\u25b6 ", style="bold magenta")
            label.append(agent, style="bold magenta")
        self.console.print()
        try:
            self.console.rule(label, style="dim")
        except UnicodeEncodeError:
            turn_prefix = f"Ход {turn} · " if turn > 0 else ""
            self.console.print(f"--- [{turn_prefix}{agent}] ---", style="bold magenta")

    def turn_summary(
        self,
        model: str,
        iterations: int,
        tool_calls: int,
        files_changed: int,
        tokens: int,
        cost_usd: float,
        elapsed: float = 0.0,
    ) -> None:
        """Print a compact one-line turn summary after the response."""
        def _k(n: int) -> str:
            return f"{n / 1000:.1f}k" if n >= 1000 else str(n)

        parts: list[tuple[str, str]] = []
        parts.append((model, "cyan"))
        if iterations > 1:
            parts.append((f"шаг {iterations}", "dim"))
        if tool_calls:
            noun = "инструмент" if tool_calls == 1 else "инструментов"
            parts.append((f"{tool_calls} {noun}", "dim"))
        if files_changed:
            noun = "файл" if files_changed == 1 else "файлов"
            parts.append((f"{files_changed} {noun}", "dim"))
        parts.append((_k(tokens) + " токенов", "dim"))
        if cost_usd > 0:
            cost_fmt = f"${cost_usd:.4f}".rstrip("0").rstrip(".")
            parts.append((cost_fmt, "dim"))
        if elapsed > 0:
            parts.append((f"{elapsed:.1f}с", "dim"))

        line = Text()
        line.append("  ")
        for i, (text, style) in enumerate(parts):
            if i > 0:
                line.append(" \u00b7 ", style="dim")
            line.append(text, style=style)
        self.console.print(line)

    def session_status(
        self,
        model: str,
        agent: str,
        turns: int,
        tokens: int,
        cost_usd: float,
        branch: str = "",
    ) -> None:
        """Print a one-line session status bar before the prompt."""
        tokens_str = f"{tokens / 1000:.1f}k" if tokens >= 1000 else str(tokens)
        cost_str = f"${cost_usd:.4f}" if cost_usd else ""
        session_part = f"{tokens_str} tok"
        if cost_str:
            session_part += f" \u00b7 {cost_str}"
        status = Text()
        if branch:
            status.append(f" \ue0a0 {branch}", style="bold blue")   # nerd-font branch glyph
            status.append("  ", style="dim")
        status.append(f"{model}", style="cyan")
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
            branch_prefix = f"\ue0a0 {branch}  " if branch else ""
            self.console.print(f"{branch_prefix}{status}", style="dim")

    # Tools that only read data — excluded from the summary panel.
    _READ_ONLY_TOOLS = frozenset(("file_read", "glob", "grep"))

    def summary(self, tool_calls: list[dict]) -> None:
        """Render a deduplicated summary panel of write actions only."""
        seen: set[str] = set()
        lines: list[str] = []

        for tc in tool_calls:
            name = tc["tool"]
            if name in self._READ_ONLY_TOOLS:
                continue

            args = tc["args"]
            if name == "file_write":
                entry = f"  Создан: {args.get('path', '?')}"
            elif name == "file_edit":
                entry = f"  Изменён: {args.get('path', '?')}"
            elif name == "bash":
                cmd = str(args.get("command", "?"))[:60]
                entry = f"  Выполнено: {cmd}"
            elif name == "git":
                entry = f"  Git: {args.get('subcommand', '?')}"
            else:
                entry = f"  {name}"

            if entry not in seen:
                seen.add(entry)
                lines.append(entry)

        if lines:
            content = "\n".join(lines)
            panel = Panel(content, title="Итог", border_style="cyan", expand=False)
            self.console.print(panel)

    def agent_selected(self, agent_name: str) -> None:
        """Print a dim one-liner when the router auto-selects an agent."""
        line = Text()
        style_info = self._AGENT_STYLES.get(agent_name.lower())
        if style_info:
            icon, color = style_info
            line.append(f"  Авто \u2192 ", style="dim")
            line.append(icon, style=color)
            line.append(agent_name, style=color)
        else:
            line.append(f"  Авто \u2192 {agent_name}", style="dim")
        self.console.print(line)

    def model_fallback(self, failed: str, fallback: str, reason: str) -> None:
        """Print a notification when the model router falls back to a backup model."""
        line = Text()
        line.append("  \u21a9 ", style="bold yellow")
        line.append("Переключение: ", style="dim")
        line.append(failed, style="dim red")
        line.append(" \u2192 ", style="dim")
        line.append(fallback, style="dim green")
        line.append(f"  ({reason})", style="dim")
        self.console.print(line)

    def context_warning(self, pct: int) -> None:
        """Print a warning when context usage exceeds the threshold."""
        line = Text()
        line.append("  \u26a0 ", style="bold yellow")
        line.append(f"Контекст заполнен на {pct}%", style="yellow")
        line.append(" \u2014 используйте ", style="dim")
        line.append("/clear", style="bold")
        line.append(" для сброса", style="dim")
        self.console.print(line)

    # Map exception class names / keywords to user-friendly messages
    _FRIENDLY_ERRORS: list[tuple[str, str, str]] = [
        ("LLMRetryExhausted",   "Все модели недоступны.",
         "Повторите попытку через минуту или выберите другую модель через /model."),
        ("TokenBudgetExceeded", "Достигнут лимит токенов.",
         "Используйте /clear для сброса сессии или /budget для проверки лимитов."),
        ("TimeoutError",        "Превышено время ожидания.",
         "Попробуйте более простую задачу или отключите отладку: /debug off."),
        ("ConnectionError",     "Сетевая ошибка.",
         "Проверьте подключение к интернету и адрес API."),
        ("RateLimitError",      "Превышен лимит запросов API.",
         "Подождите немного и повторите попытку или смените модель через /model."),
    ]

    def friendly_error(self, exc: Exception) -> None:
        """Display a structured, user-friendly error instead of a raw traceback."""
        exc_type = type(exc).__name__
        exc_msg = str(exc)

        title, hint = None, None
        for key, t, h in self._FRIENDLY_ERRORS:
            if key in exc_type or key.lower() in exc_msg.lower():
                title, hint = t, h
                break

        if title is None:
            # Generic: show type + first 120 chars of message
            title = f"Ошибка агента ({exc_type})"
            hint = exc_msg[:120] if exc_msg else "Подробности недоступны."

        header = Text()
        header.append("  \u2717 ", style="bold red")
        header.append(title, style="bold red")
        self.console.print(header)

        if hint:
            body = Text()
            body.append(f"    {hint}", style="dim")
            self.console.print(body)

    def suggestions(self, items: list[str]) -> None:
        """Print a dim numbered list of next-step hints."""
        if not items:
            return
        line = Text()
        line.append("  Что дальше: ", style="dim")
        for i, hint in enumerate(items):
            if i > 0:
                line.append("  |  ", style="dim")
            line.append(f"{i + 1}. {hint}", style="dim")
        self.console.print(line)

    def divider(self) -> None:
        """Print a horizontal divider."""
        try:
            self.console.rule(style="dim")
        except UnicodeEncodeError:
            self.console.print("-" * 60, style="dim")
