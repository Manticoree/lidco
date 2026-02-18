"""Streaming display component — shows LLM output in real-time.

Uses a persistent Rich Live status bar pinned to the bottom of the terminal.
All reasoning text and tool events print above via console.print(), while the
status bar continuously shows: current phase, elapsed time, and token count.
"""

from __future__ import annotations

import sys
import time
from typing import Any

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
        self._label = "Thinking"
        self._start = time.monotonic()
        self._frame = 0
        self._total_tokens = 0
        self._total_cost_usd = 0.0

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
        text.append(f" · {elapsed_str}", style="dim")
        if self._total_tokens > 0:
            text.append(f" · {tokens_str} tokens", style="dim")
        if self._total_cost_usd > 0:
            text.append(f" · ${self._total_cost_usd:.4f}", style="dim")
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

    def __init__(self, console: Console) -> None:
        self._console = console
        self._has_content = False
        self._needs_newline = False

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
        "file_read": "Reading",
        "glob": "Matching",
        "grep": "Searching for",
    }

    def on_tool_event(
        self,
        event: str,
        tool_name: str,
        args: dict,
        result: object | None = None,
    ) -> None:
        """Display a tool call event above the status bar.

        Read-only tools (file_read, glob, grep) show a dim inline marker on
        start and are silent on end — no result output.
        """
        if tool_name in self._READ_ONLY_TOOLS:
            if event == "start":
                self._on_read_only_start(tool_name, args)
            return

        if event == "start":
            self._on_tool_start(tool_name, args)
        elif event == "end":
            self._on_tool_end(tool_name, args, result)

    def _on_read_only_start(self, tool_name: str, args: dict) -> None:
        """Print a dim one-line marker for a read-only tool."""
        self._ensure_newline()
        label = self._READ_ONLY_LABELS.get(tool_name, tool_name)
        key_arg = _extract_key_arg(tool_name, args)
        line = Text()
        line.append("  ")
        line.append("\u21b3 ", style="dim")
        line.append(f"{label} {key_arg}" if key_arg else label, style="dim")
        self._console.print(line)
        self._needs_newline = False

    def _on_tool_start(self, tool_name: str, args: dict) -> None:
        self._ensure_newline()
        if tool_name == "bash":
            cmd = str(args.get("command", ""))
            line = Text()
            line.append("  ")
            line.append("$ ", style="bold cyan")
            line.append(cmd[:120] + "..." if len(cmd) > 120 else cmd, style="dim")
            self._console.print(line)
        else:
            key_arg = _extract_key_arg(tool_name, args)
            line = Text()
            line.append("  ")
            line.append("\u26a1 ", style="bold yellow")
            line.append(tool_name, style="bold")
            if key_arg:
                line.append(f" {key_arg}", style="dim")
            self._console.print(line)
        self._needs_newline = False

    def _on_tool_end(
        self, tool_name: str, args: dict, result: object | None
    ) -> None:
        if result is not None and hasattr(result, "success"):
            if result.success:
                self._print_success(tool_name, args, result)
            else:
                error_msg = getattr(result, "error", "failed") or "failed"
                if len(error_msg) > 80:
                    error_msg = error_msg[:77] + "..."
                line = Text()
                line.append("  ")
                line.append("\u2717 ", style="bold red")
                line.append(error_msg, style="dim red")
                self._console.print(line)
        self._needs_newline = False
        self._console.print()

    def _print_success(
        self, tool_name: str, args: dict, result: object
    ) -> None:
        if tool_name == "file_edit":
            self._print_edit_diff(args, result)
        elif tool_name == "file_write":
            self._print_file_write(args, result)
        elif tool_name == "bash":
            self._print_bash_output(result)
        else:
            brief = _brief_result(tool_name, result)
            line = Text()
            line.append("  ")
            line.append("\u2713 ", style="bold green")
            line.append(brief, style="dim")
            self._console.print(line)

    def _print_edit_diff(self, args: dict, result: object) -> None:
        path = str(args.get("path", ""))
        old = str(args.get("old_string", ""))
        new = str(args.get("new_string", ""))

        header = Text()
        header.append("  ")
        header.append("\u270f ", style="bold yellow")
        header.append(path, style="bold")
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
        brief.append(output.strip()[:80] if output.strip() else "Applied edit", style="dim")
        self._console.print(brief)

    def _print_file_write(self, args: dict, result: object) -> None:
        path = str(args.get("path", ""))
        content = str(args.get("content", ""))
        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)

        line = Text()
        line.append("  ")
        line.append("\u270f ", style="bold yellow")
        line.append(f"Created {path}", style="bold")
        line.append(f" ({line_count} lines)", style="dim")
        self._console.print(line)

    def _print_bash_output(self, result: object) -> None:
        output = getattr(result, "output", "") or ""
        lines = output.strip().splitlines()
        max_lines = 15
        shown = lines[:max_lines]

        for ln in shown:
            row = Text()
            row.append(f"    {ln}", style="dim")
            self._console.print(row)
        if len(lines) > max_lines:
            trunc = Text()
            trunc.append(f"    ... ({len(lines) - max_lines} more lines)", style="dim")
            self._console.print(trunc)

    def on_status(self, status: str) -> None:
        """Update the status bar label (e.g. 'Thinking (step 2)', 'Tool: file_read')."""
        self._status_bar.label = status

    def update_tokens(self, total: int, total_cost_usd: float = 0.0) -> None:
        """Update the token count and cost displayed in the status bar."""
        self._status_bar.total_tokens = total
        self._status_bar.total_cost_usd = total_cost_usd

    def finish(self) -> None:
        """Stop the status bar and finalize output."""
        if self._live is not None:
            try:
                self._live.stop()
            except Exception:
                pass
            self._live = None
        if self._needs_newline:
            self._console.print()
            self._needs_newline = False
        # Flush underlying file handle so output appears immediately
        # before prompt_toolkit blocks on user input.
        f = self._console.file
        if f is not None and hasattr(f, "flush"):
            try:
                f.flush()
            except Exception:
                pass

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
    if tool_name in ("file_read", "file_write", "file_edit"):
        return str(args.get("path", ""))
    if tool_name == "bash":
        cmd = str(args.get("command", ""))
        return cmd[:60] + "..." if len(cmd) > 60 else cmd
    if tool_name in ("grep", "glob"):
        return str(args.get("pattern", ""))
    if tool_name == "git":
        return str(args.get("subcommand", ""))
    return ""


def _brief_result(tool_name: str, result: object) -> str:
    """Create a brief summary of a tool result for display."""
    output = getattr(result, "output", "") or ""

    if tool_name == "file_read":
        line_count = output.count("\n")
        return f"{line_count} lines"
    if tool_name in ("file_write", "file_edit"):
        return "Applied edit"
    if tool_name == "bash":
        lines = output.strip().split("\n")
        if len(lines) <= 1:
            text = lines[0] if lines else "done"
            return text[:80] if len(text) > 80 else text
        return f"{len(lines)} lines of output"
    if tool_name in ("grep", "glob"):
        lines = [ln for ln in output.strip().split("\n") if ln]
        return f"{len(lines)} matches"
    if tool_name == "git":
        return output.strip()[:60] if output.strip() else "done"
    return output[:60] if output else "done"
