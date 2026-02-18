"""Web fetch tool — download and parse web pages."""

from __future__ import annotations

import re
from typing import Any

try:
    import httpx

    _HTTPX_AVAILABLE = True
except ImportError:
    httpx = None  # type: ignore[assignment]
    _HTTPX_AVAILABLE = False

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


def _strip_html(html: str) -> str:
    """Convert HTML to plain text preserving basic structure."""
    # Remove script and style blocks
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Convert block-level tags to newlines
    text = re.sub(r"<(br|p|div|h[1-6]|li|tr)[^>]*>", "\n", text, flags=re.IGNORECASE)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode common entities
    for entity, char in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&nbsp;", " "), ("&quot;", '"')]:
        text = text.replace(entity, char)
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class WebFetchTool(BaseTool):
    """Fetch and parse a web page."""

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return "Fetch web page as plain text."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="url",
                type="string",
                description="The URL to fetch.",
            ),
            ToolParameter(
                name="max_length",
                type="integer",
                description="Maximum length of returned text in characters.",
                required=False,
                default=5000,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.ASK

    async def _run(self, **kwargs: Any) -> ToolResult:
        url: str = kwargs["url"]
        max_length: int = kwargs.get("max_length", 5000)

        if not _HTTPX_AVAILABLE:
            return ToolResult(
                output="",
                success=False,
                error="httpx is not installed. Run: pip install httpx",
            )

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.TimeoutException:
            return ToolResult(
                output="",
                success=False,
                error=f"Request timed out after 15 seconds: {url}",
            )
        except Exception as e:
            return ToolResult(
                output="",
                success=False,
                error=f"Fetch failed: {e}",
            )

        content_type = response.headers.get("content-type", "")
        raw = response.text

        if "html" in content_type or raw.strip().startswith("<"):
            text = _strip_html(raw)
        else:
            text = raw

        if len(text) > max_length:
            text = text[:max_length] + "\n\n[Truncated]"

        return ToolResult(
            output=text,
            success=True,
            metadata={"url": url, "length": len(text)},
        )
