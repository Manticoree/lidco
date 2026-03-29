"""Web search grounding -- search the web and inject context into prompts."""

from __future__ import annotations

import re
import urllib.request
import urllib.parse
from dataclasses import dataclass
from typing import Optional, Callable


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


class WebSearchGrounder:
    """Search the web and ground prompts with search context."""

    def __init__(self, search_fn: Optional[Callable] = None):
        self._search_fn = search_fn

    def search(self, query: str, n: int = 5) -> list[SearchResult]:
        """Search for *query* and return top *n* results.

        If a *search_fn* was injected, delegates to it.
        Otherwise scrapes DuckDuckGo HTML via urllib.
        Never raises on network error -- returns a list with an error entry.
        """
        if self._search_fn is not None:
            try:
                return self._search_fn(query, n)
            except Exception as exc:
                return [SearchResult(title="Error", url="", snippet=str(exc))]
        try:
            return self._scrape_ddg(query, n)
        except Exception as exc:
            return [SearchResult(title="Error", url="", snippet=str(exc))]

    def grounded_prompt(self, query: str, base_prompt: str, n: int = 3) -> str:
        """Search for *query* and prepend top-*n* snippets as context."""
        results = self.search(query, n)
        if not results:
            return base_prompt

        lines = ["Web search context:"]
        for r in results:
            lines.append(f"- [{r.title}]: {r.snippet}")
        lines.append("")
        lines.append(base_prompt)
        return "\n".join(lines)

    def _scrape_ddg(self, query: str, n: int) -> list[SearchResult]:
        """Scrape DuckDuckGo HTML search results."""
        encoded = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; LidcoBot/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        results: list[SearchResult] = []
        # Parse result blocks from DDG HTML
        blocks = re.findall(
            r'<a[^>]+class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
            r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
            html,
            re.DOTALL,
        )
        for href, title_html, snippet_html in blocks[:n]:
            title = re.sub(r"<[^>]+>", "", title_html).strip()
            snippet = re.sub(r"<[^>]+>", "", snippet_html).strip()
            # DDG wraps URLs in a redirect; extract actual URL
            actual_url = href
            m = re.search(r"uddg=([^&]+)", href)
            if m:
                actual_url = urllib.parse.unquote(m.group(1))
            results.append(SearchResult(title=title, url=actual_url, snippet=snippet))

        return results
