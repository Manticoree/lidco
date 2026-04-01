"""Cache Warmer — pre-populate prompt cache from predicted keys."""
from __future__ import annotations

from dataclasses import dataclass

from lidco.cache.prompt_cache import PromptCache


@dataclass(frozen=True)
class WarmResult:
    """Result of a cache warming operation."""

    warmed: int
    skipped: int
    failed: int


class CacheWarmer:
    """Pre-warm a PromptCache with known entries.

    Parameters
    ----------
    cache:
        The PromptCache to warm.
    """

    def __init__(self, cache: PromptCache) -> None:
        self._cache = cache

    def warm(self, entries: tuple[tuple[str, str], ...]) -> WarmResult:
        """Populate cache with *(key, value)* pairs.

        Skips keys that already exist in the cache.
        """
        warmed = 0
        skipped = 0
        failed = 0
        for key, value in entries:
            try:
                existing = self._cache.get(key)
                if existing is not None:
                    skipped += 1
                    continue
                self._cache.put(key, value)
                warmed += 1
            except Exception:
                failed += 1
        return WarmResult(warmed=warmed, skipped=skipped, failed=failed)

    def predict_keys(self, history: tuple[str, ...]) -> tuple[str, ...]:
        """Predict likely cache keys from recent history.

        Simple heuristic: return unique recent keys that appear more than once.
        """
        counts: dict[str, int] = {}
        for key in history:
            counts[key] = counts.get(key, 0) + 1
        return tuple(k for k, c in counts.items() if c > 1)


__all__ = ["WarmResult", "CacheWarmer"]
