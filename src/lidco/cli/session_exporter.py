"""Q55/373 — Session export to Markdown, HTML, or JSON.

Usage::

    exporter = SessionExporter(history, session_id="my-session")
    path = exporter.export(format="md", output_dir=Path(".lidco/exports"))
"""
from __future__ import annotations

import json
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any


# Minimal inline CSS for HTML export (no external dependencies)
_HTML_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       max-width: 900px; margin: 2em auto; padding: 0 1em; line-height: 1.6;
       background: #1e1e1e; color: #d4d4d4; }
h1 { color: #569cd6; border-bottom: 1px solid #333; padding-bottom: .4em; }
.turn { margin-bottom: 1.5em; }
.user { background: #252526; border-left: 3px solid #569cd6;
        padding: .6em 1em; border-radius: 4px; }
.assistant { background: #252526; border-left: 3px solid #4ec9b0;
             padding: .6em 1em; border-radius: 4px; }
.role { font-size: .75em; font-weight: bold; text-transform: uppercase;
        margin-bottom: .3em; }
.user .role { color: #569cd6; }
.assistant .role { color: #4ec9b0; }
pre { background: #0d0d0d; padding: 1em; overflow-x: auto; border-radius: 4px; }
code { font-family: 'Fira Code', 'Cascadia Code', monospace; font-size: .9em; }
"""


def _escape_html(text: str) -> str:
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _md_to_html_code_blocks(text: str) -> str:
    """Very minimal code block conversion for HTML export."""
    import re
    # ```lang\n...\n``` → <pre><code>...</code></pre>
    text = re.sub(
        r"```(\w*)\n(.*?)\n```",
        lambda m: f"<pre><code>{_escape_html(m.group(2))}</code></pre>",
        text,
        flags=re.DOTALL,
    )
    # inline `code`
    text = re.sub(r"`([^`]+)`", lambda m: f"<code>{_escape_html(m.group(1))}</code>", text)
    # newlines → <br>
    text = text.replace("\n", "<br>")
    return text


class SessionExporter:
    """Export a conversation history to various formats."""

    def __init__(
        self,
        history: list[dict[str, Any]],
        session_id: str = "session",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._history = history
        self._session_id = session_id
        self._metadata = metadata or {}

    def export(
        self,
        format: str = "md",
        output_dir: Path | None = None,
    ) -> Path:
        """Export and return the output file path.

        Args:
            format: One of ``"md"``, ``"html"``, ``"json"``.
            output_dir: Directory to write the file. Defaults to current dir.
        """
        output_dir = output_dir or Path.cwd()
        output_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = f"{self._session_id}_{ts}"

        if format == "json":
            path = output_dir / f"{stem}.json"
            path.write_text(self._to_json(), encoding="utf-8")
        elif format == "html":
            path = output_dir / f"{stem}.html"
            path.write_text(self._to_html(), encoding="utf-8")
        else:  # default: md
            path = output_dir / f"{stem}.md"
            path.write_text(self._to_markdown(), encoding="utf-8")

        return path

    # ── Format renderers ──────────────────────────────────────────────────────

    def _to_markdown(self) -> str:
        lines: list[str] = [
            f"# Сессия: {self._session_id}",
            f"*Экспортировано: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            "",
        ]
        if self._metadata:
            lines += [
                "## Метаданные",
                "```json",
                json.dumps(self._metadata, ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        for i, msg in enumerate(self._history, 1):
            role = msg.get("role", "unknown")
            content = msg.get("content") or ""
            if isinstance(content, list):
                parts = [p.get("text", "") for p in content if isinstance(p, dict)]
                content = "\n".join(parts)
            if not content:
                continue
            role_label = "👤 Пользователь" if role == "user" else "🤖 Ассистент"
            lines += [f"### {role_label} (шаг {i})", "", content, ""]
        return "\n".join(lines)

    def _to_html(self) -> str:
        title = f"Сессия: {self._session_id}"
        turns_html: list[str] = []
        for i, msg in enumerate(self._history, 1):
            role = msg.get("role", "unknown")
            content = msg.get("content") or ""
            if isinstance(content, list):
                parts = [p.get("text", "") for p in content if isinstance(p, dict)]
                content = "\n".join(parts)
            if not content:
                continue
            role_label = "Пользователь" if role == "user" else "Ассистент"
            body = _md_to_html_code_blocks(_escape_html(content))
            turns_html.append(
                f'<div class="turn {role}">'
                f'<div class="role">{role_label}</div>'
                f"<div>{body}</div>"
                f"</div>"
            )
        body_html = "\n".join(turns_html)
        return textwrap.dedent(f"""\
            <!DOCTYPE html>
            <html lang="ru">
            <head>
              <meta charset="UTF-8">
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <title>{_escape_html(title)}</title>
              <style>{_HTML_CSS}</style>
            </head>
            <body>
              <h1>{_escape_html(title)}</h1>
              <p><em>Экспортировано: {datetime.now().strftime('%Y-%m-%d %H:%M')}</em></p>
              {body_html}
            </body>
            </html>
        """)

    def _to_json(self) -> str:
        data = {
            "session_id": self._session_id,
            "exported_at": datetime.now().isoformat(),
            "metadata": self._metadata,
            "messages": [
                {
                    "role": m.get("role"),
                    "content": m.get("content") or "",
                }
                for m in self._history
                if m.get("content")
            ],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)
