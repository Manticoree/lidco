"""Lightweight token estimation without external dependencies.

Uses the ~4 chars per token heuristic which is accurate enough for
deciding when to prune conversations or warn about context limits.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lidco.llm.base import Message

# Average characters per token (English / code mix).
_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in *text*.

    Uses a simple chars/4 heuristic — no tiktoken dependency needed.
    """
    if not text:
        return 0
    return max(1, len(text) // _CHARS_PER_TOKEN)


def estimate_message_tokens(message: Message) -> int:
    """Estimate tokens for a single conversation message.

    Accounts for role overhead (~4 tokens) and tool_call JSON if present.
    """
    import json

    tokens = 4  # role / message overhead
    tokens += estimate_tokens(message.content)

    if message.tool_calls:
        tokens += estimate_tokens(json.dumps(message.tool_calls))

    if message.name:
        tokens += estimate_tokens(message.name)

    return tokens


def estimate_conversation_tokens(messages: list[Message]) -> int:
    """Estimate total tokens for an entire conversation."""
    return sum(estimate_message_tokens(m) for m in messages)
