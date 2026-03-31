"""Side-question fork for single-turn questions without context pollution -- Q162."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class SideQuestionResult:
    """Result of a side question."""

    question: str
    answer: str
    tokens_used: int


class SideQuestionManager:
    """Manage side questions that don't pollute the main conversation context.

    Side questions are processed in isolation -- they never modify or read
    from the main conversation history.  Results are kept in a bounded
    history ring for later inspection.
    """

    def __init__(self, max_history: int = 20) -> None:
        self._max_history = max_history
        self._history: deque[SideQuestionResult] = deque(maxlen=max_history)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ask(self, question: str, context: str = "") -> SideQuestionResult:
        """Process *question* in isolated context and return a result.

        The optional *context* provides background information for the
        question but is **not** persisted in the main conversation.

        A simple heuristic answer is returned when no LLM backend is
        wired in; callers may override with an async LLM call.
        """
        if not question.strip():
            result = SideQuestionResult(
                question=question,
                answer="No question provided.",
                tokens_used=0,
            )
            self._history.append(result)
            return result

        # Build an isolated prompt (context + question).
        prompt_parts: list[str] = []
        if context:
            prompt_parts.append(context)
        prompt_parts.append(question)
        prompt_text = "\n".join(prompt_parts)

        # Token estimate: ~4 chars per token for prompt + answer stub.
        estimated_tokens = max(1, len(prompt_text) // 4)

        answer = f"[side-question] {question.strip()}"

        result = SideQuestionResult(
            question=question,
            answer=answer,
            tokens_used=estimated_tokens,
        )
        self._history.append(result)
        return result

    def history(self) -> list[SideQuestionResult]:
        """Return the full side-question history (oldest first)."""
        return list(self._history)

    def clear_history(self) -> None:
        """Discard all recorded side-question results."""
        self._history.clear()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def max_history(self) -> int:
        return self._max_history
