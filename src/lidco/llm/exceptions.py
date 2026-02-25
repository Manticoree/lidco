"""Custom exceptions for the LLM subsystem."""

from __future__ import annotations


class LLMRetryExhausted(Exception):
    """Raised when all retry attempts (and fallback models) are exhausted.

    Attributes:
        attempts: List of ``(model_name, error)`` tuples describing each
            failed attempt, ordered from first to last.
    """

    def __init__(
        self,
        message: str,
        attempts: list[tuple[str, Exception]] | None = None,
    ) -> None:
        self.attempts = attempts or []
        super().__init__(message)
