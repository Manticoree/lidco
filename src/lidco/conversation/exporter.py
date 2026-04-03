"""Conversation export to multiple formats (Q248)."""
from __future__ import annotations

import json
from html import escape as _html_escape


class ConversationExporter:
    """Export a conversation message list to markdown, JSON, or HTML."""

    def __init__(self, messages: list[dict]) -> None:
        self._messages = list(messages)
        self._include_stats = True

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def with_stats(self, include: bool = True) -> "ConversationExporter":
        """Toggle stats appendix.  Returns a new exporter (immutable)."""
        new = ConversationExporter(self._messages)
        new._include_stats = include
        return new

    # ------------------------------------------------------------------
    # Formats
    # ------------------------------------------------------------------

    def to_markdown(self) -> str:
        """Render the conversation as Markdown."""
        lines: list[str] = ["# Conversation Export", ""]
        for i, msg in enumerate(self._messages):
            role = msg.get("role", "unknown")
            content = msg.get("content") or ""
            lines.append(f"## Turn {i + 1} ({role})")
            lines.append("")
            lines.append(content)
            lines.append("")
        if self._include_stats:
            lines.append(self._stats_section("markdown"))
        return "\n".join(lines)

    def to_json(self) -> str:
        """Render the conversation as pretty JSON."""
        payload: dict = {"messages": self._messages}
        if self._include_stats:
            payload["stats"] = self._stats_dict()
        return json.dumps(payload, indent=2, default=str)

    def to_html(self) -> str:
        """Render the conversation as basic HTML."""
        parts: list[str] = [
            "<!DOCTYPE html>",
            "<html><head><meta charset='utf-8'><title>Conversation</title></head>",
            "<body>",
            "<h1>Conversation Export</h1>",
        ]
        for i, msg in enumerate(self._messages):
            role = _html_escape(msg.get("role", "unknown"))
            content = _html_escape(msg.get("content") or "")
            parts.append(f"<h2>Turn {i + 1} ({role})</h2>")
            parts.append(f"<pre>{content}</pre>")
        if self._include_stats:
            parts.append(self._stats_section("html"))
        parts.append("</body></html>")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def export(self, format: str = "markdown") -> str:
        """Export using the named *format* (markdown | json | html)."""
        dispatch = {
            "markdown": self.to_markdown,
            "json": self.to_json,
            "html": self.to_html,
        }
        fn = dispatch.get(format.lower())
        if fn is None:
            raise ValueError(f"Unsupported format: {format}")
        return fn()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _stats_dict(self) -> dict:
        total = len(self._messages)
        roles: dict[str, int] = {}
        total_chars = 0
        for msg in self._messages:
            r = msg.get("role", "unknown")
            roles[r] = roles.get(r, 0) + 1
            total_chars += len(msg.get("content") or "")
        return {
            "total_turns": total,
            "roles": roles,
            "total_chars": total_chars,
        }

    def _stats_section(self, fmt: str) -> str:
        stats = self._stats_dict()
        if fmt == "html":
            return (
                "<h2>Stats</h2>"
                f"<p>Total turns: {stats['total_turns']}, "
                f"Total chars: {stats['total_chars']}</p>"
            )
        # markdown
        roles = ", ".join(f"{r}: {c}" for r, c in sorted(stats["roles"].items()))
        return (
            "---\n"
            f"**Stats** | Turns: {stats['total_turns']} | "
            f"Chars: {stats['total_chars']} | Roles: {roles}"
        )
