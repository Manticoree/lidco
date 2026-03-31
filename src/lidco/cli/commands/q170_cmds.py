"""Q170 CLI commands: /copy, /paste, /browse, /clipboard."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def _get_clipboard():
    from lidco.bridge.clipboard import ClipboardManager

    if "clipboard" not in _state:
        _state["clipboard"] = ClipboardManager()
    return _state["clipboard"]


def _get_reader():
    from lidco.bridge.page_reader import PageReader

    if "reader" not in _state:
        _state["reader"] = PageReader()
    return _state["reader"]


def _get_web_ctx():
    from lidco.bridge.web_context import WebContextProvider

    if "web_ctx" not in _state:
        _state["web_ctx"] = WebContextProvider(_get_reader())
    return _state["web_ctx"]


def _get_paste_mode():
    from lidco.bridge.paste_mode import PasteMode

    if "paste_mode" not in _state:
        _state["paste_mode"] = PasteMode()
    return _state["paste_mode"]


def register(registry) -> None:
    """Register Q170 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def copy_handler(args: str) -> str:
        """Copy Nth-latest response to clipboard."""
        cm = _get_clipboard()
        parts = args.strip().split()
        n = 1
        if parts:
            try:
                n = int(parts[0])
            except ValueError:
                return "Usage: /copy [N] — copy Nth-latest response (default: last)"
        # Use last_message from registry if available
        content = getattr(registry, "last_message", "") or ""
        if not content:
            return "Nothing to copy (no recent response)."
        entry = cm.copy(content, source="user")
        tag = " (code)" if entry.is_code else ""
        return f"Copied to clipboard{tag} ({len(content)} chars)."

    async def paste_handler(args: str) -> str:
        """Paste from clipboard into context."""
        cm = _get_clipboard()
        content = cm.paste()
        if not content:
            # Fall back to latest history entry
            hist = cm.history(limit=1)
            if hist:
                content = hist[0].content
        if not content:
            return "Clipboard is empty."
        return f"Pasted from clipboard:\n{content}"

    async def browse_handler(args: str) -> str:
        """Fetch and show page content."""
        url = args.strip()
        if not url:
            return "Usage: /browse <url>"
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            reader = _get_reader()
            page = reader.read(url)
        except Exception as exc:
            return f"Failed to fetch {url}: {exc}"
        parts: list[str] = []
        parts.append(f"Title: {page.title or '(none)'}")
        parts.append(f"URL: {page.url}")
        if page.code_blocks:
            parts.append(f"Code blocks: {len(page.code_blocks)}")
        text_preview = page.text[:1000] if page.text else "(no text)"
        parts.append("")
        parts.append(text_preview)
        if len(page.text) > 1000:
            parts.append(f"\n... ({len(page.text)} chars total)")
        return "\n".join(parts)

    async def clipboard_handler(args: str) -> str:
        """Manage clipboard: history, clear."""
        cm = _get_clipboard()
        sub = args.strip().lower()

        if sub == "clear":
            cm.clear()
            return "Clipboard history cleared."

        if sub == "history" or not sub:
            hist = cm.history(limit=10)
            if not hist:
                return "Clipboard history is empty."
            lines: list[str] = [f"Clipboard history ({len(hist)} entries):"]
            for i, entry in enumerate(hist, 1):
                preview = entry.content[:60].replace("\n", " ")
                tag = " [code]" if entry.is_code else ""
                lines.append(f"  {i}. ({entry.source}){tag} {preview}...")
            return "\n".join(lines)

        return (
            "Usage: /clipboard [history|clear]\n"
            "  history — show recent clipboard entries\n"
            "  clear   — clear clipboard history"
        )

    registry.register(SlashCommand("copy", "Copy response to clipboard", copy_handler))
    registry.register(SlashCommand("paste", "Paste from clipboard into context", paste_handler))
    registry.register(SlashCommand("browse", "Fetch and show web page content", browse_handler))
    registry.register(SlashCommand("clipboard", "Manage clipboard history", clipboard_handler))
