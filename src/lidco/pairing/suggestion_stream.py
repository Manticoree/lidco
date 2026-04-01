"""Real-time code suggestion stream for AI pair programming."""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field


class SuggestionType(str, enum.Enum):
    """Type of code suggestion."""

    INSERT = "insert"
    REPLACE = "replace"
    DELETE = "delete"
    COMPLETE = "complete"


@dataclass(frozen=True)
class CodeSuggestion:
    """A single code suggestion."""

    type: SuggestionType
    content: str
    file: str = ""
    line: int = 0
    confidence: float = 0.5
    explanation: str = ""


class SuggestionStream:
    """Real-time code suggestion stream with debounce and history."""

    def __init__(self, debounce_ms: float = 300.0) -> None:
        self._debounce_ms = debounce_ms
        self._contexts: list[dict[str, object]] = []
        self._pending: list[CodeSuggestion] = []
        self._accepted: list[CodeSuggestion] = []
        self._last_generate: float = 0.0

    def add_context(self, file: str, content: str, cursor_line: int = 0) -> None:
        """Add file context for suggestion generation."""
        self._contexts.append({
            "file": file,
            "content": content,
            "cursor_line": cursor_line,
        })

    def generate(self, prompt: str = "") -> list[CodeSuggestion]:
        """Generate suggestions based on accumulated context."""
        now = time.monotonic() * 1000
        if now - self._last_generate < self._debounce_ms and self._last_generate > 0:
            return list(self._pending)
        self._last_generate = now

        suggestions: list[CodeSuggestion] = []
        for ctx in self._contexts:
            file = str(ctx["file"])
            content = str(ctx["content"])
            cursor = int(ctx.get("cursor_line", 0) or 0)
            lines = content.splitlines()

            if prompt:
                suggestions.append(CodeSuggestion(
                    type=SuggestionType.COMPLETE,
                    content=prompt,
                    file=file,
                    line=cursor,
                    confidence=0.7,
                    explanation=f"Completion for prompt: {prompt[:50]}",
                ))

            if lines:
                current_line = lines[min(cursor, len(lines) - 1)] if cursor < len(lines) else ""
                if current_line.rstrip().endswith(":"):
                    suggestions.append(CodeSuggestion(
                        type=SuggestionType.INSERT,
                        content="    pass",
                        file=file,
                        line=cursor + 1,
                        confidence=0.6,
                        explanation="Add placeholder body",
                    ))
                if "TODO" in content:
                    suggestions.append(CodeSuggestion(
                        type=SuggestionType.REPLACE,
                        content="# DONE",
                        file=file,
                        line=cursor,
                        confidence=0.4,
                        explanation="Resolve TODO comment",
                    ))

        self._pending = suggestions
        return list(self._pending)

    def accept(self, index: int) -> CodeSuggestion | None:
        """Accept a pending suggestion by index."""
        if 0 <= index < len(self._pending):
            suggestion = self._pending.pop(index)
            self._accepted.append(suggestion)
            return suggestion
        return None

    def reject(self, index: int) -> bool:
        """Reject a pending suggestion by index."""
        if 0 <= index < len(self._pending):
            self._pending.pop(index)
            return True
        return False

    def pending(self) -> list[CodeSuggestion]:
        """Return current pending suggestions."""
        return list(self._pending)

    def clear(self) -> None:
        """Clear all pending suggestions and contexts."""
        self._pending.clear()
        self._contexts.clear()

    def history(self) -> list[CodeSuggestion]:
        """Return accepted suggestion history."""
        return list(self._accepted)
