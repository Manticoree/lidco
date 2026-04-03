"""Response parser — extract code blocks, tool calls, and thinking sections."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParsedResponse:
    """Structured representation of a parsed LLM response."""

    text_blocks: list[str] = field(default_factory=list)
    code_blocks: list[dict[str, str]] = field(default_factory=list)
    tool_calls: list[dict[str, str]] = field(default_factory=list)
    thinking: str = ""


_CODE_BLOCK_RE = re.compile(
    r"```(\w*)\n(.*?)```", re.DOTALL,
)

_TOOL_USE_RE = re.compile(
    r"<tool_use>\s*<name>(.*?)</name>\s*<input>(.*?)</input>\s*</tool_use>",
    re.DOTALL,
)

_THINKING_RE = re.compile(
    r"<thinking>(.*?)</thinking>", re.DOTALL,
)


class ResponseParser:
    """Parse raw LLM response text into structured parts."""

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @staticmethod
    def extract_code_blocks(text: str) -> list[dict[str, str]]:
        """Return list of ``{language, code}`` dicts from fenced blocks."""
        blocks: list[dict[str, str]] = []
        for m in _CODE_BLOCK_RE.finditer(text):
            blocks.append({
                "language": m.group(1) or "text",
                "code": m.group(2),
            })
        return blocks

    @staticmethod
    def extract_tool_calls(text: str) -> list[dict[str, str]]:
        """Return list of ``{name, input}`` dicts from ``<tool_use>`` tags."""
        calls: list[dict[str, str]] = []
        for m in _TOOL_USE_RE.finditer(text):
            calls.append({
                "name": m.group(1).strip(),
                "input": m.group(2).strip(),
            })
        return calls

    @staticmethod
    def separate_thinking(text: str) -> tuple[str, str]:
        """Split *text* into ``(thinking, output)`` on ``<thinking>`` tags.

        If no thinking tags are present, returns ``("", text)``.
        """
        m = _THINKING_RE.search(text)
        if m is None:
            return ("", text)
        thinking = m.group(1).strip()
        output = (_THINKING_RE.sub("", text)).strip()
        return (thinking, output)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def parse(self, text: str) -> ParsedResponse:
        """Parse *text* into a :class:`ParsedResponse`."""
        thinking, remaining = self.separate_thinking(text)
        code_blocks = self.extract_code_blocks(remaining)
        tool_calls = self.extract_tool_calls(remaining)

        # Text blocks = everything outside code fences and tool_use tags
        stripped = _CODE_BLOCK_RE.sub("", remaining)
        stripped = _TOOL_USE_RE.sub("", stripped)
        text_blocks = [
            block.strip()
            for block in stripped.split("\n\n")
            if block.strip()
        ]

        return ParsedResponse(
            text_blocks=text_blocks,
            code_blocks=code_blocks,
            tool_calls=tool_calls,
            thinking=thinking,
        )
