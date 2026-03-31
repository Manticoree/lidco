"""Q131: Fluent builder for structured prompts."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List


class PromptBuilder:
    """Build structured prompts fluently."""

    def __init__(self) -> None:
        self._parts: list[dict] = []  # {"type": ..., "role": ..., "content": ...}

    # --- fluent methods ------------------------------------------------------

    def system(self, text: str) -> "PromptBuilder":
        self._parts.append({"type": "message", "role": "system", "content": text})
        return self

    def user(self, text: str) -> "PromptBuilder":
        self._parts.append({"type": "message", "role": "user", "content": text})
        return self

    def assistant(self, text: str) -> "PromptBuilder":
        self._parts.append({"type": "message", "role": "assistant", "content": text})
        return self

    def context(self, label: str, content: str) -> "PromptBuilder":
        """Add a labelled context block: <label>content</label>."""
        block = f"<{label}>{content}</{label}>"
        self._parts.append({"type": "context", "role": "user", "content": block})
        return self

    def examples(self, pairs: list[tuple[str, str]]) -> "PromptBuilder":
        """Add (input, output) example pairs."""
        lines = []
        for inp, out in pairs:
            lines.append(f"Input: {inp}")
            lines.append(f"Output: {out}")
        self._parts.append(
            {"type": "examples", "role": "user", "content": "\n".join(lines)}
        )
        return self

    def instructions(self, text: str) -> "PromptBuilder":
        self._parts.append({"type": "instructions", "role": "user", "content": text})
        return self

    def reset(self) -> "PromptBuilder":
        self._parts.clear()
        return self

    # --- output methods ------------------------------------------------------

    def build(self) -> str:
        """Build full prompt as a single string."""
        sections: list[str] = []
        for part in self._parts:
            role = part["role"].upper()
            content = part["content"]
            sections.append(f"{role}: {content}")
        return "\n\n".join(sections)

    def build_messages(self) -> list[dict]:
        """Build as list of {role, content} message dicts."""
        messages: list[dict] = []
        for part in self._parts:
            messages.append({"role": part["role"], "content": part["content"]})
        return messages

    def token_estimate(self, chars_per_token: float = 4.0) -> int:
        """Rough token estimate based on character count."""
        total_chars = sum(len(p["content"]) for p in self._parts)
        return math.ceil(total_chars / chars_per_token)
