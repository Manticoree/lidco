"""Strategy pattern — interchangeable algorithms with context (stdlib only)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")
R = TypeVar("R")


class Strategy(ABC, Generic[T, R]):
    """Abstract base for a strategy."""

    @abstractmethod
    def execute(self, data: T) -> R:
        """Execute the strategy on *data*."""

    @property
    def name(self) -> str:
        return type(self).__name__


class LambdaStrategy(Strategy):
    """Wrap a plain callable as a strategy."""

    def __init__(self, fn: Callable, name: str = "") -> None:
        self._fn = fn
        self._name = name or getattr(fn, "__name__", "lambda")

    def execute(self, data: Any) -> Any:
        return self._fn(data)

    @property
    def name(self) -> str:
        return self._name


class Context(Generic[T, R]):
    """
    Strategy context — holds the current strategy and executes it.

    Parameters
    ----------
    strategy:
        Initial strategy.  Can be swapped at runtime.
    """

    def __init__(self, strategy: Strategy | None = None) -> None:
        self._strategy: Strategy | None = strategy
        self._history: list[str] = []

    def set_strategy(self, strategy: Strategy) -> None:
        self._strategy = strategy
        self._history.append(strategy.name)

    def execute(self, data: Any) -> Any:
        if self._strategy is None:
            raise RuntimeError("No strategy set")
        return self._strategy.execute(data)

    @property
    def current_strategy(self) -> Strategy | None:
        return self._strategy

    @property
    def strategy_history(self) -> list[str]:
        return list(self._history)


# ---------------------------------------------------------------- Sorting strategies

class SortStrategy(Strategy):
    """Base for list sorting strategies."""

    @abstractmethod
    def execute(self, data: list) -> list:
        """Return a new sorted list."""


class AscendingSortStrategy(SortStrategy):
    def execute(self, data: list) -> list:
        return sorted(data)


class DescendingSortStrategy(SortStrategy):
    def execute(self, data: list) -> list:
        return sorted(data, reverse=True)


class KeySortStrategy(SortStrategy):
    """Sort by a key function."""

    def __init__(self, key: Callable, reverse: bool = False) -> None:
        self._key = key
        self._reverse = reverse

    def execute(self, data: list) -> list:
        return sorted(data, key=self._key, reverse=self._reverse)


# ---------------------------------------------------------------- Compression strategies

class CompressionStrategy(Strategy):
    """Base for string compression strategies."""

    @abstractmethod
    def execute(self, data: str) -> str:
        """Return compressed/encoded string."""


class NoCompressionStrategy(CompressionStrategy):
    def execute(self, data: str) -> str:
        return data


class RLECompressionStrategy(CompressionStrategy):
    """Simple run-length encoding."""

    def execute(self, data: str) -> str:
        if not data:
            return ""
        result = []
        count = 1
        for i in range(1, len(data)):
            if data[i] == data[i - 1]:
                count += 1
            else:
                result.append(f"{count}{data[i-1]}" if count > 1 else data[i-1])
                count = 1
        result.append(f"{count}{data[-1]}" if count > 1 else data[-1])
        return "".join(result)
