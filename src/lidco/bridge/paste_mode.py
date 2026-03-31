"""Copy/paste mode for bridging with web LLMs."""
from __future__ import annotations

import re

_CODE_BLOCK_RE = re.compile(r"```(?:\w+)?\s*\n(.*?)```", re.DOTALL)


class PasteMode:
    """Format prompts for web LLMs and parse pasted responses."""

    def format_for_web(self, context: str, question: str) -> str:
        """Format *context* and *question* for pasting into a web LLM interface."""
        parts: list[str] = []
        if context.strip():
            parts.append("Context:")
            parts.append(context.strip())
            parts.append("")
        parts.append("Question:")
        parts.append(question.strip())
        return "\n".join(parts)

    def parse_response(self, raw: str) -> dict:
        """Extract code blocks and text from a pasted LLM response."""
        code_blocks: list[str] = []
        for m in _CODE_BLOCK_RE.finditer(raw):
            block = m.group(1).strip()
            if block:
                code_blocks.append(block)
        # Text is everything outside code fences
        text = _CODE_BLOCK_RE.sub("", raw).strip()
        return {
            "text": text,
            "code_blocks": code_blocks,
            "has_code": len(code_blocks) > 0,
        }

    def roundtrip(self, context: str, question: str, response: str) -> dict:
        """Full cycle: format prompt, parse response, return structured result."""
        formatted = self.format_for_web(context, question)
        parsed = self.parse_response(response)
        return {
            "prompt": formatted,
            "context": context,
            "question": question,
            "response": parsed,
        }
