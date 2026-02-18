"""Web search tool using DuckDuckGo."""

from __future__ import annotations

from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


class WebSearchTool(BaseTool):
    """Search the web using DuckDuckGo."""

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

        lines: list[str] = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            url = r.get("href", r.get("link", ""))
            snippet = r.get("body", r.get("snippet", ""))
            lines.append(f"{i}. **{title}**\n   URL: {url}\n   {snippet}")

        output = f"Search results for: {query}\n\n" + "\n\n".join(lines)
        return ToolResult(
            output=output,
            success=True,
            metadata={"query": query, "result_count": len(results)},
        )
