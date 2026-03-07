"""Web search tool using DuckDuckGo."""

from __future__ import annotations

import time
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult

# 5-minute TTL for cached results
_CACHE_TTL_SECONDS = 300.0


class WebSearchTool(BaseTool):
    """Search the web using DuckDuckGo.

    Results are cached in-memory for 5 minutes to avoid duplicate network calls
    within the same session.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Cache: query -> (cached_at: float, output: str)
        self._cache: dict[str, tuple[float, str]] = {}

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Web search via DuckDuckGo. Returns titles, URLs, snippets."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="query",
                type="string",
                description="The search query.",
            ),
            ToolParameter(
                name="max_results",
                type="integer",
                description="Maximum number of results to return.",
                required=False,
                default=5,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.ASK

    async def _run(self, **kwargs: Any) -> ToolResult:
        query: str = kwargs["query"]
        max_results: int = kwargs.get("max_results", 5)

        # Check cache first
        cached = self._cache.get(query)
        if cached is not None:
            cached_at, cached_output = cached
            if time.monotonic() - cached_at < _CACHE_TTL_SECONDS:
                return ToolResult(
                    output=cached_output,
                    success=True,
                    metadata={"query": query, "result_count": 0, "cached": True},
                )

        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return ToolResult(
                output="",
                success=False,
                error=(
                    "duckduckgo-search is not installed. "
                    "Run: pip install duckduckgo-search"
                ),
            )

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
        except Exception as e:
            return ToolResult(
                output="",
                success=False,
                error=f"Search failed: {e}",
            )

        if not results:
            return ToolResult(output="No results found.", success=True)

        result_count = len(results)
        lines: list[str] = [
            f"## Summary",
            f"Found {result_count} result{'s' if result_count != 1 else ''} for: {query}",
            "",
        ]
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            url = r.get("href", r.get("link", ""))
            snippet = r.get("body", r.get("snippet", ""))
            lines.append(f"{i}. **{title}**\n   URL: {url}\n   {snippet}")
            if i < result_count:
                lines.append("---")

        output = "\n".join(lines)

        # Store in cache on success
        self._cache[query] = (time.monotonic(), output)

        return ToolResult(
            output=output,
            success=True,
            metadata={"query": query, "result_count": result_count},
        )
