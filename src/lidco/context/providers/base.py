"""Abstract base for context providers."""
from __future__ import annotations

from abc import ABC, abstractmethod


class ContextProvider(ABC):
    """Abstract base for context providers that inject data into the system prompt."""

    def __init__(self, name: str, priority: int = 50, max_tokens: int = 2000) -> None:
        self._name = name
        self._priority = priority
        self._max_tokens = max_tokens

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    @abstractmethod
    async def fetch(self) -> str:
        """Fetch the context content."""
        ...
