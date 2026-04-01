"""Format thinking blocks for display."""
from __future__ import annotations

from dataclasses import dataclass, field


_DECISION_KEYWORDS = ("decision:", "conclusion:", "therefore")


@dataclass(frozen=True)
class ViewOptions:
    """Options controlling thinking-block display."""

    collapsed: bool = False
    max_lines: int = 50
    highlight_decisions: bool = True
    show_tokens: bool = True


class ThinkingViewer:
    """Format thinking blocks for terminal display."""

    def __init__(self, options: ViewOptions | None = None) -> None:
        self._options = options or ViewOptions()

    def format_block(
        self, content: str, turn: int = 0, tokens: int = 0
    ) -> str:
        """Format a single thinking block with header."""
        header = f"--- Turn {turn}"
        if self._options.show_tokens and tokens:
            header += f" ({tokens} tokens)"
        header += " ---"

        body = content
        if self._options.collapsed:
            body = self.collapse(body, self._options.max_lines)
        if self._options.highlight_decisions:
            body = self.highlight_decisions(body)

        return f"{header}\n{body}"

    def format_all(self, blocks: list[dict]) -> str:
        """Format multiple blocks with separators."""
        parts: list[str] = []
        for blk in blocks:
            parts.append(
                self.format_block(
                    blk.get("content", ""),
                    turn=blk.get("turn", 0),
                    tokens=blk.get("tokens", 0),
                )
            )
        return "\n\n".join(parts)

    def collapse(self, content: str, max_lines: int = 10) -> str:
        """Collapse long content keeping first 5 + last 5 lines."""
        lines = content.splitlines()
        if len(lines) <= max_lines:
            return content
        head = lines[:5]
        tail = lines[-5:]
        collapsed = len(lines) - 10
        return "\n".join([*head, f"... ({collapsed} lines collapsed)", *tail])

    def highlight_decisions(self, content: str) -> str:
        """Prefix decision/conclusion/therefore lines with >>>."""
        out: list[str] = []
        for line in content.splitlines():
            lower = line.lower().strip()
            if any(kw in lower for kw in _DECISION_KEYWORDS):
                out.append(f">>> {line}")
            else:
                out.append(line)
        return "\n".join(out)

    def diff(self, block_a: str, block_b: str) -> str:
        """Simple line diff between two thinking blocks."""
        lines_a = block_a.splitlines()
        lines_b = block_b.splitlines()
        result: list[str] = []
        max_len = max(len(lines_a), len(lines_b))
        for i in range(max_len):
            la = lines_a[i] if i < len(lines_a) else ""
            lb = lines_b[i] if i < len(lines_b) else ""
            if la == lb:
                result.append(f"  {la}")
            else:
                if la:
                    result.append(f"- {la}")
                if lb:
                    result.append(f"+ {lb}")
        return "\n".join(result)

    def summary(self) -> str:
        """Summary of viewer configuration."""
        opts = self._options
        return (
            f"ThinkingViewer: collapsed={opts.collapsed}, "
            f"max_lines={opts.max_lines}, "
            f"highlight={opts.highlight_decisions}"
        )
