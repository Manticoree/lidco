"""Session / report exporter — Cursor export / documentation parity.

Exports a conversation (list of ``{"role": ..., "content": ...}`` dicts)
to Markdown or HTML.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExportConfig:
    """Configuration for a session export."""

    format: str = "markdown"  # "markdown" | "html"
    include_metadata: bool = True
    max_messages: int | None = None
    title: str = "LIDCO Session Export"


@dataclass
class ExportResult:
    """Result of a session export operation."""

    content: str
    format: str
    message_count: int


_ROLE_LABEL = {
    "user": "User",
    "assistant": "Assistant",
    "system": "System",
    "tool": "Tool",
}

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 860px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; }}
  .msg {{ margin-bottom: 1.5rem; border-left: 3px solid #ccc; padding-left: 1rem; }}
  .msg.user {{ border-color: #4f8ef7; }}
  .msg.assistant {{ border-color: #2ecc71; }}
  .msg.system {{ border-color: #e67e22; }}
  .role {{ font-weight: bold; font-size: 0.85rem; text-transform: uppercase; margin-bottom: 0.25rem; color: #555; }}
  pre {{ background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; }}
  code {{ background: #f5f5f5; padding: 0.1em 0.3em; border-radius: 3px; }}
  .meta {{ font-size: 0.8rem; color: #999; margin-top: 0.25rem; }}
</style>
</head>
<body>
<h1>{title}</h1>
{body}
</body>
</html>
"""

# B9: Match code fences that may be unterminated (end-of-string counts as close)
_CODE_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)(?:```|$)", re.DOTALL)
# Inline code — non-greedy, one backtick on each side
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")


class SessionExporter:
    """Export conversation messages to Markdown or HTML.

    Usage::

        exporter = SessionExporter()
        result = exporter.export(messages, ExportConfig(format="html"))
        exporter.save(result, "session.html")
    """

    def export(
        self,
        messages: list[dict],
        config: ExportConfig | None = None,
    ) -> ExportResult:
        """Export *messages* using *config* (defaults to Markdown)."""
        cfg = config or ExportConfig()
        subset = messages
        if cfg.max_messages is not None:
            subset = messages[-cfg.max_messages :]

        if cfg.format == "html":
            content = self.export_html(
                subset,
                include_metadata=cfg.include_metadata,
                title=cfg.title,
            )
        else:
            content = self.export_markdown(
                subset, include_metadata=cfg.include_metadata
            )

        return ExportResult(
            content=content,
            format=cfg.format,
            message_count=len(subset),
        )

    def export_markdown(
        self,
        messages: list[dict],
        include_metadata: bool = True,
    ) -> str:
        """Render *messages* as Markdown."""
        parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            label = _ROLE_LABEL.get(role, role.capitalize())

            parts.append(f"## {label}")
            if not isinstance(content, str):
                content = str(content)
            parts.append(content)
            if include_metadata and "name" in msg:
                parts.append(f"*({msg['name']})*")
            parts.append("")  # blank line between messages

        return "\n".join(parts).rstrip() + "\n"

    def export_html(
        self,
        messages: list[dict],
        include_metadata: bool = True,
        title: str = "LIDCO Session Export",
    ) -> str:
        """Render *messages* as a self-contained HTML page."""
        blocks: list[str] = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            label = _ROLE_LABEL.get(role, role.capitalize())

            if not isinstance(content, str):
                content = str(content)

            escaped = self._md_to_html_basic(content)
            meta_html = ""
            if include_metadata and "name" in msg:
                meta_html = (
                    f'<div class="meta">{html.escape(str(msg["name"]))}</div>'
                )

            blocks.append(
                f'<div class="msg {html.escape(role)}">'
                f'<div class="role">{html.escape(label)}</div>'
                f"{escaped}"
                f"{meta_html}"
                f"</div>"
            )

        body = "\n".join(blocks)
        return _HTML_TEMPLATE.format(title=html.escape(title), body=body)

    def save(self, result: ExportResult, path: str | Path) -> Path:
        """Write *result.content* to *path* and return the resolved path."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(result.content, encoding="utf-8")
        return out.resolve()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _md_to_html_basic(self, text: str) -> str:
        """Minimal Markdown→HTML: code fences, inline code, paragraphs.

        Processing order:
        1. Extract and escape code fences (stored as placeholders)
        2. Escape remaining text (prevents XSS)
        3. Replace inline code
        4. Split into paragraphs
        """
        # Step 1: Replace code fences with placeholders to protect them
        # from HTML escaping and paragraph splitting
        fence_store: list[str] = []

        def _store_fence(m: re.Match) -> str:
            escaped_code = html.escape(m.group(1))
            fence_store.append(f"<pre><code>{escaped_code}</code></pre>")
            return f"\x00FENCE{len(fence_store) - 1}\x00"

        # B9: pattern handles unterminated fences via (?:```|$)
        text = _CODE_FENCE_RE.sub(_store_fence, text)

        # Step 2: Escape all remaining HTML special chars
        text = html.escape(text)

        # Step 3: Restore placeholders and replace inline code
        def _restore_fence(m: re.Match) -> str:
            return fence_store[int(m.group(1))]

        text = re.sub(r"\x00FENCE(\d+)\x00", _restore_fence, text)

        # Inline code (operates on already-escaped text)
        text = _INLINE_CODE_RE.sub(
            lambda m: f"<code>{m.group(1)}</code>", text
        )

        # Step 4: Paragraphs — split on blank lines
        paragraphs = re.split(r"\n{2,}", text.strip())
        result_parts: list[str] = []
        for p in paragraphs:
            p = p.strip()
            if p.startswith("<pre>") or p.startswith("\x00FENCE"):
                result_parts.append(p)
            else:
                result_parts.append(f"<p>{p.replace(chr(10), '<br>')}</p>")
        return "\n".join(result_parts)
