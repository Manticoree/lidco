"""Clipboard manager with injectable copy/paste functions."""
from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class ClipboardEntry:
    """A single clipboard history entry."""

    content: str
    timestamp: float
    source: str  # "user", "agent", or "paste"
    is_code: bool


_CODE_KEYWORDS = frozenset({
    "def", "class", "import", "from", "return", "if", "else", "elif",
    "for", "while", "try", "except", "finally", "with", "async", "await",
    "function", "const", "let", "var", "export", "interface", "type",
    "public", "private", "static", "void", "int", "string",
})

_BRACE_PATTERN = re.compile(r"[{}\[\]();]")
_INDENT_PATTERN = re.compile(r"^[ \t]{2,}\S", re.MULTILINE)


def _noop_copy(text: str) -> None:
    pass


def _noop_paste() -> str:
    return ""


class ClipboardManager:
    """Manages clipboard history with injectable copy/paste backends."""

    def __init__(
        self,
        max_history: int = 50,
        copy_fn: Optional[Callable[[str], None]] = None,
        paste_fn: Optional[Callable[[], str]] = None,
    ) -> None:
        self._max_history = max_history
        self._history: deque[ClipboardEntry] = deque(maxlen=max_history)
        self._copy_fn: Callable[[str], None] = copy_fn or _noop_copy
        self._paste_fn: Callable[[], str] = paste_fn or _noop_paste

    @property
    def max_history(self) -> int:
        return self._max_history

    def copy(self, content: str, source: str = "agent") -> ClipboardEntry:
        """Copy content to clipboard and store in history."""
        self._copy_fn(content)
        entry = ClipboardEntry(
            content=content,
            timestamp=time.time(),
            source=source,
            is_code=self.detect_code(content),
        )
        self._history.append(entry)
        return entry

    def paste(self) -> str:
        """Return the latest content from the paste function."""
        return self._paste_fn()

    def history(self, limit: int = 10) -> list[ClipboardEntry]:
        """Return the most recent *limit* entries (newest first)."""
        items = list(self._history)
        items.reverse()
        return items[:limit]

    def clear(self) -> None:
        """Clear all clipboard history."""
        self._history.clear()

    @staticmethod
    def detect_code(content: str) -> bool:
        """Heuristic check whether *content* looks like source code."""
        if not content or not content.strip():
            return False
        lines = content.splitlines()
        # Check for indentation patterns
        if _INDENT_PATTERN.search(content):
            indent_count = sum(1 for ln in lines if re.match(r"^[ \t]{2,}\S", ln))
            if indent_count >= 2:
                return True
        # Check for braces / semicolons
        brace_count = len(_BRACE_PATTERN.findall(content))
        if brace_count >= 3:
            return True
        # Check for code keywords
        words = set(re.findall(r"\b\w+\b", content))
        keyword_hits = words & _CODE_KEYWORDS
        if len(keyword_hits) >= 2:
            return True
        return False
