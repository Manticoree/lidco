"""URL context provider with simple in-memory cache."""
from __future__ import annotations

import time
from urllib.request import urlopen
from urllib.error import URLError

from .base import ContextProvider


class URLContextProvider(ContextProvider):
    """Fetches a URL and injects its content. Cached for `cache_ttl` seconds."""

    def __init__(
        self,
        name: str,
        url: str,
        cache_ttl: int = 300,
        priority: int = 50,
        max_tokens: int = 2000,
    ) -> None:
        super().__init__(name, priority, max_tokens)
        self._url = url
        self._cache_ttl = cache_ttl
        self._cached_content: str | None = None
        self._cached_at: float = 0.0

    @property
    def url(self) -> str:
        return self._url

    async def fetch(self) -> str:
        now = time.time()
        if self._cached_content is not None and (now - self._cached_at) < self._cache_ttl:
            return self._cached_content
        try:
            with urlopen(self._url, timeout=10) as resp:
                content = resp.read().decode("utf-8", errors="replace")
        except (URLError, OSError) as exc:
            return f"[URL fetch failed: {exc}]"
        self._cached_content = content
        self._cached_at = now
        return content
