"""FallbackChain — try multiple providers in order (stdlib only)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class FallbackResult:
    """Result of a fallback chain execution."""

    value: Any
    source: str
    attempts: list[dict] = field(default_factory=list)
    fallback_used: bool = False


class FallbackChain:
    """Try a sequence of callables in order until one succeeds."""

    def __init__(self) -> None:
        self._chain: list[tuple[str, Callable, dict]] = []

    def add(self, name: str, fn: Callable, **kwargs) -> None:
        """Add a fallback option with *name*."""
        self._chain.append((name, fn, kwargs))

    def execute(self, *args, **kwargs) -> FallbackResult:
        """Try each fallback in order (sync). Raises last exception if all fail."""
        attempts: list[dict] = []
        last_exc: Exception | None = None

        for idx, (name, fn, stored_kw) in enumerate(self._chain):
            merged = {**stored_kw, **kwargs}
            try:
                result = fn(*args, **merged)
                return FallbackResult(
                    value=result,
                    source=name,
                    attempts=attempts,
                    fallback_used=idx > 0,
                )
            except Exception as exc:
                last_exc = exc
                attempts.append({
                    "name": name,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                })

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("FallbackChain is empty")

    async def async_execute(self, *args, **kwargs) -> FallbackResult:
        """Try each fallback in order (async). Raises last exception if all fail."""
        attempts: list[dict] = []
        last_exc: Exception | None = None

        for idx, (name, fn, stored_kw) in enumerate(self._chain):
            merged = {**stored_kw, **kwargs}
            try:
                result = await fn(*args, **merged)
                return FallbackResult(
                    value=result,
                    source=name,
                    attempts=attempts,
                    fallback_used=idx > 0,
                )
            except Exception as exc:
                last_exc = exc
                attempts.append({
                    "name": name,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                })

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("FallbackChain is empty")

    def remove(self, name: str) -> None:
        """Remove a fallback by name."""
        self._chain = [(n, fn, kw) for n, fn, kw in self._chain if n != name]

    def clear(self) -> None:
        """Remove all fallbacks."""
        self._chain.clear()

    def __len__(self) -> int:
        return len(self._chain)
