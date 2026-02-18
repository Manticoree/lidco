"""Thinking timer display — shows elapsed time while AI is processing."""

from __future__ import annotations

import time

from rich.console import ConsoleRenderable, RichCast
from rich.text import Text


class ThinkingTimer(ConsoleRenderable, RichCast):
    """A Rich renderable that shows a spinner with elapsed time.

    Displays like Claude Code:
      ● Thinking... (3s)
      ● Routing to coder... (1s)
      ● Running tool: file_write (5s)
    """

    SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
    FALLBACK_FRAMES = ("|", "/", "-", "\\")

    def __init__(self, label: str = "Thinking") -> None:
        self._label = label
        self._start = time.monotonic()
        self._frame_idx = 0
        self._total_tokens: int = 0

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

    def _tokens_str(self) -> str:
        if self._total_tokens == 0:
            return ""
        if self._total_tokens < 1000:
            return f"{self._total_tokens} tokens"
        return f"{self._total_tokens / 1000:.1f}k tokens"

    def _elapsed_str(self) -> str:
        elapsed = time.monotonic() - self._start
        if elapsed < 60:
            return f"{elapsed:.0f}s"
        minutes = int(elapsed) // 60
        seconds = int(elapsed) % 60
        return f"{minutes}m {seconds}s"

    def __rich__(self) -> Text:
        self._frame_idx = (self._frame_idx + 1) % len(self.SPINNER_FRAMES)

        try:
            frame = self.SPINNER_FRAMES[self._frame_idx]
        except UnicodeEncodeError:
            frame = self.FALLBACK_FRAMES[self._frame_idx % len(self.FALLBACK_FRAMES)]

        elapsed = self._elapsed_str()
        tokens = self._tokens_str()
        text = Text()
        text.append(f"  {frame} ", style="bold magenta")
        text.append(self._label, style="bold")
        text.append(f" ({elapsed})", style="dim")
        if tokens:
            text.append(f" | {tokens}", style="dim cyan")
        return text

    def __rich_console__(self, console, options):
        yield self.__rich__()
