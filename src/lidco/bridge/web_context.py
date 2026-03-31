"""Web context provider — resolve @url mentions and inject fetched content."""
from __future__ import annotations

import re
from collections import OrderedDict
from typing import Optional

from lidco.bridge.page_reader import PageContent, PageReader

_URL_MENTION_RE = re.compile(r"@(https?://\S+)")


class WebContextProvider:
    """Fetch web pages referenced via @url mentions and inject summaries."""

    def __init__(self, reader: PageReader, max_cache: int = 20) -> None:
        self._reader = reader
        self._max_cache = max_cache
        self._cache: OrderedDict[str, PageContent] = OrderedDict()

    def resolve_mention(self, text: str) -> list[PageContent]:
        """Find all @url patterns in *text*, fetch each, return results."""
        urls = _URL_MENTION_RE.findall(text)
        results: list[PageContent] = []
        for url in urls:
            page = self._fetch_cached(url)
            results.append(page)
        return results

    def get_cached(self, url: str) -> Optional[PageContent]:
        """Return cached page content or None."""
        if url in self._cache:
            self._cache.move_to_end(url)
            return self._cache[url]
        return None

    def inject_context(self, prompt: str) -> str:
        """Replace @url mentions with fetched content summaries."""
        urls = _URL_MENTION_RE.findall(prompt)
        if not urls:
            return prompt
        result = prompt
        for url in urls:
            page = self._fetch_cached(url)
            summary = self._summarize(page)
            result = result.replace(f"@{url}", summary, 1)
        return result

    def clear_cache(self) -> None:
        """Clear all cached pages."""
        self._cache.clear()

    def _fetch_cached(self, url: str) -> PageContent:
        """Fetch with LRU cache."""
        if url in self._cache:
            self._cache.move_to_end(url)
            return self._cache[url]
        page = self._reader.read(url)
        self._cache[url] = page
        if len(self._cache) > self._max_cache:
            self._cache.popitem(last=False)
        return page

    @staticmethod
    def _summarize(page: PageContent) -> str:
        """Build a short summary block for injection."""
        parts: list[str] = []
        parts.append(f"[Web: {page.title or page.url}]")
        text = page.text[:500] if page.text else "(no text)"
        parts.append(text)
        if page.code_blocks:
            parts.append(f"({len(page.code_blocks)} code block(s))")
        return "\n".join(parts)
