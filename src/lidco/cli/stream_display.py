"""Streaming display component — shows LLM output in real-time.

Uses a persistent Rich Live status bar pinned to the bottom of the terminal.
All reasoning text and tool events print above via console.print(), while the
status bar continuously shows: current phase, elapsed time, and token count.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any

logger = logging.getLogger(__name__)

from rich.console import Console, ConsoleOptions, RenderableType, RenderResult
from rich.live import Live
from rich.text import Text


class _StatusBar:
    """Persistent bottom bar showing phase, elapsed time, and token count.

    Rendered by Rich.Live at ~4 fps.  Example output:
        ⠹ Thinking (step 1) · 3s · 1.2k tokens
    """

    FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
    FALLBACK = ("|", "/", "-", "\\")

    def __init__(self) -> None:
        self._label = "Обработка"
        self._start = time.monotonic()
        self._frame = 0
        self._total_tokens = 0
        self._total_cost_usd = 0.0
        self._phase_steps: list[tuple[str, str]] = []  # (name, "active"|"done"|"pending")
        self._phase_elapsed: dict[str, float] = {}  # name → elapsed seconds when done
        self._current_step: int = 0
        self._max_step: int = 0
        # Q55/374: context window usage meter
        self._ctx_used: int = 0
        self._ctx_max: int = 0

    @property
    def label(self) -> str:
        return self._label

    @label.setter
    def label(self, value: str) -> None:
        self._label = value

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    @total_tokens.setter
    def total_tokens(self, value: int) -> None:
        self._total_tokens = value

    @property
    def total_cost_usd(self) -> float:
        return self._total_cost_usd

    @total_cost_usd.setter
    def total_cost_usd(self, value: float) -> None:
        self._total_cost_usd = value

    def set_step(self, current: int, maximum: int) -> None:
        """Update the iteration counter shown in the status bar."""
        self._current_step = current
        self._max_step = maximum

    def set_context_usage(self, used_tokens: int, max_tokens: int) -> None:
        """Q55/374 — Update the context window usage shown in the status bar."""
        self._ctx_used = max(0, used_tokens)
        self._ctx_max = max(1, max_tokens)

    def set_phase(self, name: str, status: str) -> None:
        """Update or append a named phase step.

        Args:
            name: Display name of the phase (e.g. "Plan", "Execute", "Review").
            status: One of "active", "done", or "pending".

        Rebuilds the list atomically so that Rich's refresh thread iterating
        the old list reference sees a consistent snapshot even without a lock.
        """
        updated = False
        new_steps: list[tuple[str, str]] = []
        for pname, pstatus in self._phase_steps:
            if pname == name:
                new_steps.append((name, status))
                updated = True
            else:
                new_steps.append((pname, pstatus))
        if not updated:
            new_steps.append((name, status))
        self._phase_steps = new_steps
        if status == "done":
            elapsed = time.monotonic() - self._start
            self._phase_elapsed[name] = elapsed

    def __rich__(self) -> Text:
        self._frame = (self._frame + 1) % len(self.FRAMES)
        try:
            char = self.FRAMES[self._frame]
        except UnicodeEncodeError:
            char = self.FALLBACK[self._frame % len(self.FALLBACK)]

        elapsed = time.monotonic() - self._start
        if elapsed < 60:
            elapsed_str = f"{elapsed:.0f}s"
        else:
            elapsed_str = f"{int(elapsed) // 60}m {int(elapsed) % 60}s"

        tokens_str = _format_tokens(self._total_tokens)

        text = Text()
        text.append(f"  {char} ", style="bold magenta")
        text.append(self._label, style="bold")
        if self._current_step > 0 and self._max_step > 0:
            text.append(f" [{self._current_step}/{self._max_step}]", style="cyan")
        text.append(f" · {elapsed_str}", style="dim")
        if self._total_tokens > 0:
            text.append(f" · {tokens_str} tokens", style="dim")
        if self._total_cost_usd > 0:
            text.append(f" · ${self._total_cost_usd:.4f}", style="dim")
        # Q55/374: context window meter
        if self._ctx_max > 0 and self._ctx_used > 0:
            pct = min(100, int(self._ctx_used * 100 / self._ctx_max))
            filled = pct // 10
            bar = "█" * filled + "░" * (10 - filled)
            if pct >= 85:
                bar_style = "bold red"
            elif pct >= 70:
                bar_style = "bold yellow"
            else:
                bar_style = "dim green"
            text.append(f" · [{bar}] {pct}%", style=bar_style)
        if self._phase_steps:
            text.append("  ", style="dim")
            for j, (pname, pstatus) in enumerate(self._phase_steps):
                if j > 0:
                    text.append(" \u2192 ", style="dim")
                if pstatus == "done":
                    ph_elapsed = self._phase_elapsed.get(pname)
                    if ph_elapsed is not None:
                        text.append(f"{pname} \u2713", style="dim green")
                        text.append(f" {ph_elapsed:.0f}s", style="dim")
                    else:
                        text.append(f"{pname} \u2713", style="dim green")
                elif pstatus == "active":
                    text.append(pname, style="bold cyan")
                else:
                    text.append(pname, style="dim")
        return text


class StreamDisplay:
    """Displays streaming LLM output with a persistent bottom status bar.

    The status bar is pinned to the bottom of the terminal throughout the
    entire interaction. All text, tool events, and narration are printed
    above it via console.print() — Rich automatically handles the layout.

    Lifecycle:
      StreamDisplay(console)               → status bar starts
      on_status("Thinking (step 1)")       → updates bar label
      on_text_chunk("Hello ")              → text printed above bar
      on_tool_event("start", ...)          → tool block printed above bar
      update_tokens(1500)                  → updates bar token count
      finish()                             → bar removed, cleanup
    """

    # Tool categories: (icon, color, label)
    # Fallback for unknown tools: ⚡ yellow
    _TOOL_STYLES: dict[str, tuple[str, str, str]] = {
        # File operations
        "file_write":              ("✎ ", "bold yellow",   "Запись файла"),
        "file_edit":               ("✎ ", "bold yellow",   "Редактирование"),
        # Git
        "git":                     ("\u00b1 ", "bold blue",    "Git"),
        # Debug / analysis
        "run_debug_cycle":         ("\u25cf ", "bold magenta", "Цикл отладки"),
        "run_static_analysis":     ("\u25cf ", "bold magenta", "Статический анализ"),
        "check_ast_bugs":          ("\u25cf ", "bold magenta", "Проверка AST"),
        "capture_failure_locals":  ("\u25cf ", "bold magenta", "Захват переменных"),
        "capture_execution_trace": ("\u25cf ", "bold magenta", "Трассировка"),
        "analyze_imports":         ("\u25c8 ", "bold magenta", "Анализ импортов"),
        "check_dependencies":      ("\u25c8 ", "bold magenta", "Зависимости"),
        "generate_minimal_repro":  ("\u25c8 ", "bold magenta", "Воспроизведение"),
        # Test tools
        "flake_guard":             ("\u2756 ", "bold green",   "Нестабильные тесты"),
        "coverage_guard":          ("\u2756 ", "bold green",   "Покрытие"),
        "check_regressions":       ("\u2756 ", "bold green",   "Регрессия"),
        "test_autopilot":          ("\u2756 ", "bold green",   "Автопилот тестов"),
        # Error reporting
        "error_report":            ("! ",      "bold red",     "Отчёт об ошибках"),
    }

    def __init__(self, console: Console) -> None:
        self._console = console
        self._has_content = False
        self._needs_newline = False
        self._debug_mode: bool = False
        # Per-tool elapsed timing: tool_name → start timestamp
        self._tool_start_times: dict[str, float] = {}
        # Read-only tool aggregation buffer: counts per category
        self._ro_buffer: dict[str, int] = {}
        # Task 130: label saved before switching to tool name
        self._pre_tool_label: str | None = None
        # Task 133: adaptive fps
        self._tool_active: bool = False

        self._status_bar = _StatusBar()
        self._live = Live(
            self._status_bar,
            console=self._console,
            refresh_per_second=4,
            transient=True,
        )
        self._live.start()

    @property
    def live(self) -> Live | None:
        """Expose the Live instance so the REPL can pause it for permission prompts."""
        return self._live

    def on_text_chunk(self, text: str) -> None:
        """Print a text chunk inline as it arrives from the LLM."""
        if not text:
            return
        self._console.print(text, end="", highlight=False)
        self._has_content = True
        self._needs_newline = not text.endswith("\n")

    # Read-only tools — shown as a dim one-liner on start, silent on end.
    _READ_ONLY_TOOLS = frozenset(("file_read", "glob", "grep"))

    _READ_ONLY_LABELS: dict[str, str] = {
        "file_read": "Чтение",
        "glob": "Поиск файлов",
        "grep": "Поиск",
    }

    def on_tool_event(
        self,
        event: str,
        tool_name: str,
        args: dict,
        result: object | None = None,
    ) -> None:
        """Display a tool call event above the status bar.

        Read-only tools (file_read, glob, grep) are buffered and displayed as
        a single aggregated line when a non-read-only tool fires.
        """
        if tool_name in self._READ_ONLY_TOOLS:
            if event == "start":
                self._buffer_ro_tool(tool_name)
            return

        if event == "start":
            self._flush_ro_buffer()
            self._on_tool_start(tool_name, args)
        elif event == "end":
            self._on_tool_end(tool_name, args, result)

    def _buffer_ro_tool(self, tool_name: str) -> None:
        """Increment the read-only tool counter for later aggregated display."""
        self._ro_buffer[tool_name] = self._ro_buffer.get(tool_name, 0) + 1

    def _flush_ro_buffer(self) -> None:
        """Print a single aggregated line for all buffered read-only tool calls."""
        if not self._ro_buffer:
            return
        self._ensure_newline()
        reads = self._ro_buffer.get("file_read", 0)
        finds = self._ro_buffer.get("glob", 0)
        searches = self._ro_buffer.get("grep", 0)
        parts: list[str] = []
        if reads:
            parts.append(f"Прочитано {reads} {'файл' if reads == 1 else 'файлов'}")
        if finds:
            parts.append(f"Найдено {finds} {'шаблон' if finds == 1 else 'шаблонов'}")
        if searches:
            parts.append(f"Поисков: {searches}")
        if parts:
            line = Text()
            line.append("  ")
            line.append("\u21b3 ", style="dim")
            line.append(" \u00b7 ".join(parts), style="dim")
            self._console.print(line)
            self._needs_newline = False
        self._ro_buffer.clear()

    def _set_live_fps(self, fps: int) -> None:
        """Adjust Rich Live refresh rate dynamically (best-effort)."""
        live = self._live
        if live is None:
            return
        try:
            live._refresh_per_second = fps  # type: ignore[attr-defined]
        except Exception:
            pass

    def _on_tool_start(self, tool_name: str, args: dict) -> None:
        self._ensure_newline()
        self._tool_start_times[tool_name] = time.monotonic()
        # Task 130: show tool name in spinner
        self._pre_tool_label = self._status_bar.label
        style_info = self._TOOL_STYLES.get(tool_name)
        if tool_name == "bash":
            self._status_bar.label = "bash"
        elif style_info:
            self._status_bar.label = style_info[2]  # human-readable label
        else:
            self._status_bar.label = tool_name
        # Task 133: speed up refresh when tool is active
        self._tool_active = True
        self._set_live_fps(10)
        if tool_name == "bash":
            cmd = str(args.get("command", ""))
            line = Text()
            line.append("  ")
            line.append("$ ", style="bold cyan")
            line.append(cmd[:120] + "..." if len(cmd) > 120 else cmd, style="dim")
            self._console.print(line)
        else:
            style_info = self._TOOL_STYLES.get(tool_name)
            key_arg = _extract_key_arg(tool_name, args)
            line = Text()
            line.append("  ")
            if style_info:
                icon, color, label = style_info
                line.append(icon, style=color)
                line.append(label, style="bold")
            else:
                line.append("\u26a1 ", style="bold yellow")
                line.append(tool_name, style="bold")
            if key_arg:
                line.append(f" {key_arg}", style="dim")
            self._console.print(line)
        self._needs_newline = False

    def _elapsed_str(self, tool_name: str) -> str:
        """Return '[0.3s]' string for the tool, empty if no start time recorded."""
        start = self._tool_start_times.pop(tool_name, None)
        if start is None:
            return ""
        elapsed = time.monotonic() - start
        if elapsed < 0.05:
            return ""
        if elapsed < 60:
            return f" [{elapsed:.1f}s]"
        return f" [{int(elapsed) // 60}m {int(elapsed) % 60}s]"

    def _on_tool_end(
        self, tool_name: str, args: dict, result: object | None
    ) -> None:
        # Task 130: restore label; Task 133: slow down fps
        if self._pre_tool_label is not None:
            self._status_bar.label = self._pre_tool_label
            self._pre_tool_label = None
        self._tool_active = False
        self._set_live_fps(4)
        elapsed = self._elapsed_str(tool_name)
        if result is not None and hasattr(result, "success"):
            if result.success:
                self._print_success(tool_name, args, result, elapsed)
            else:
                error_msg = getattr(result, "error", "failed") or "failed"
                tb = getattr(result, "traceback_str", None)
                if self._debug_mode and tb:
                    self._print_debug_error(tool_name, error_msg, tb)
                else:
                    if len(error_msg) > 80:
                        error_msg = error_msg[:77] + "..."
                    line = Text()
                    line.append("  ")
                    line.append("\u2717 ", style="bold red")
                    line.append(error_msg, style="dim red")
                    if elapsed:
                        line.append(elapsed, style="dim")
                    self._console.print(line)
        self._needs_newline = False
        self._console.print()

    def _print_success(
        self, tool_name: str, args: dict, result: object, elapsed: str = ""
    ) -> None:
        if tool_name == "file_edit":
            self._print_edit_diff(args, result, elapsed)
        elif tool_name == "file_write":
            self._print_file_write(args, result, elapsed)
        elif tool_name == "bash":
            self._print_bash_output(result, elapsed)
        else:
            brief = _brief_result(tool_name, result)
            line = Text()
            line.append("  ")
            line.append("\u2713 ", style="bold green")
            line.append(brief, style="dim")
            if elapsed:
                line.append(elapsed, style="dim")
            self._console.print(line)

    def _print_edit_diff(self, args: dict, result: object, elapsed: str = "") -> None:
        path = str(args.get("path", ""))
        old = str(args.get("old_string", ""))
        new = str(args.get("new_string", ""))

        header = Text()
        header.append("  ")
        header.append("\u270f ", style="bold yellow")
        header.append(path, style="bold")
        if elapsed:
            header.append(elapsed, style="dim")
        self._console.print(header)

        max_lines = 10
        for prefix, text, style in (("-", old, "red"), ("+", new, "green")):
            lines = text.splitlines()
            shown = lines[:max_lines]
            for ln in shown:
                row = Text()
                row.append(f"  {prefix} ", style=style)
                row.append(ln)
                self._console.print(row)
            if len(lines) > max_lines:
                omitted = Text()
                omitted.append(f"  {prefix} ... ({len(lines) - max_lines} more lines)", style="dim")
                self._console.print(omitted)

        output = getattr(result, "output", "") or ""
        brief = Text()
        brief.append("  ")
        brief.append("\u2713 ", style="bold green")
        brief.append(output.strip()[:80] if output.strip() else "Изменение применено", style="dim")
        self._console.print(brief)

    def _print_file_write(self, args: dict, result: object, elapsed: str = "") -> None:
        path = str(args.get("path", ""))
        content = str(args.get("content", ""))
        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)

        line = Text()
        line.append("  ")
        line.append("\u270f ", style="bold yellow")
        line.append(f"Создан {path}", style="bold")
        line.append(f" ({line_count} строк)", style="dim")
        if elapsed:
            line.append(elapsed, style="dim")
        self._console.print(line)

    def _print_bash_output(self, result: object, elapsed: str = "") -> None:
        output = getattr(result, "output", "") or ""
        lines = output.strip().splitlines()
        max_tail = 5
        total = len(lines)

        if total == 0:
            return

        if total > max_tail:
            skipped = total - max_tail
            trunc = Text()
            trunc.append(f"    \u25b2 {skipped} more lines", style="dim")
            if elapsed:
                trunc.append(elapsed, style="dim")
            self._console.print(trunc)
            shown = lines[-max_tail:]
        else:
            shown = lines
            if elapsed and shown:
                # append elapsed to last shown line via separate print
                pass

        for i, ln in enumerate(shown):
            row = Text()
            row.append(f"    {ln}", style="dim")
            if elapsed and i == len(shown) - 1 and total <= max_tail:
                row.append(elapsed, style="dim")
            self._console.print(row)

    def set_debug_mode(self, enabled: bool) -> None:
        """Enable or disable inline traceback rendering on tool failures."""
        self._debug_mode = enabled

    def _print_debug_error(
        self, tool_name: str, error_msg: str, traceback_str: str
    ) -> None:
        """Render a Rich Panel with syntax-highlighted traceback (debug mode)."""
        from rich.panel import Panel
        from rich.syntax import Syntax

        # Show last 50 non-empty lines of the traceback
        lines = [ln for ln in traceback_str.splitlines() if ln.strip()]
        shown_lines = lines[-50:]
        tb_text = "\n".join(shown_lines)

        syntax = Syntax(tb_text, "python", theme="monokai", word_wrap=True)
        self._console.print(
            Panel(
                syntax,
                title=f"Tool Error: {tool_name}",
                border_style="red",
            )
        )

    _STEP_RE = __import__("re").compile(r"\(step (\d+)/(\d+)\)")

    def on_status(self, status: str) -> None:
        """Update the status bar label. Parses '(step N/M)' for iteration tracking."""
        m = self._STEP_RE.search(status)
        if m:
            self._status_bar.set_step(int(m.group(1)), int(m.group(2)))
            # Strip the step tag from the label — shown separately in the bar
            clean = self._STEP_RE.sub("", status).strip(" ·")
            self._status_bar.label = clean
        else:
            self._status_bar.label = status

    def set_phase(self, name: str, status: str) -> None:
        """Update the phase breadcrumb shown at the right of the status bar.

        Args:
            name: Phase name e.g. "Plan", "Execute", "Review".
            status: "active" (currently running), "done" (completed), "pending".
        """
        self._status_bar.set_phase(name, status)

    def update_tokens(self, total: int, total_cost_usd: float = 0.0) -> None:
        """Update the token count and cost displayed in the status bar."""
        self._status_bar.total_tokens = total
        self._status_bar.total_cost_usd = total_cost_usd

    def update_context_usage(self, used_tokens: int, max_tokens: int) -> None:
        """Q55/374 — Update context window meter in the status bar."""
        self._status_bar.set_context_usage(used_tokens, max_tokens)

    def finish(self) -> None:
        """Stop the status bar and finalize output."""
        self._flush_ro_buffer()
        if self._live is not None:
            live, self._live = self._live, None
            try:
                live.stop()
            except Exception as exc:
                logger.debug("Error stopping Live display: %s", exc)
        if self._needs_newline:
            self._console.print()
            self._needs_newline = False
        # Flush underlying file handle so output appears immediately
        # before prompt_toolkit blocks on user input.
        f = self._console.file
        if f is not None and hasattr(f, "flush"):
            try:
                f.flush()
            except Exception as exc:
                logger.debug("Error flushing console: %s", exc)

    def _ensure_newline(self) -> None:
        """Print a newline if the last output didn't end with one."""
        if self._needs_newline:
            self._console.print()
            self._needs_newline = False


def _format_tokens(total: int) -> str:
    """Format token count for display."""
    if total >= 1000:
        return f"{total / 1000:.1f}k"
    return str(total)


def _extract_key_arg(tool_name: str, args: dict) -> str:
    """Extract the most informative argument for display."""
    from pathlib import Path
    if tool_name in ("file_read", "file_write", "file_edit"):
        return Path(str(args.get("path", ""))).name
    if tool_name == "bash":
        cmd = str(args.get("command", ""))
        return cmd[:60] + "..." if len(cmd) > 60 else cmd
    if tool_name == "grep":
        pattern = str(args.get("pattern", ""))
        return f"'{pattern}'"
    if tool_name == "glob":
        return str(args.get("pattern", ""))
    if tool_name == "git":
        return str(args.get("subcommand", ""))
    return ""


def _brief_result(tool_name: str, result: object) -> str:
    """Create a brief summary of a tool result for display."""
    output = getattr(result, "output", "") or ""

    if tool_name == "file_read":
        line_count = output.count("\n")
        return f"{line_count} строк"
    if tool_name in ("file_write", "file_edit"):
        return "Изменение применено"
    if tool_name == "bash":
        lines = output.strip().split("\n")
        if len(lines) <= 1:
            text = lines[0] if lines else "готово"
            return text[:80] if len(text) > 80 else text
        return f"{len(lines)} строк вывода"
    if tool_name in ("grep", "glob"):
        lines = [ln for ln in output.strip().split("\n") if ln]
        return f"{len(lines)} совпадений"
    if tool_name == "git":
        return output.strip()[:60] if output.strip() else "готово"
    return output[:60] if output else "готово"
