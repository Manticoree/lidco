"""Debug inspector for examining individual conversation messages."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MessageInspection:
    """Result of inspecting a single message."""

    role: str
    content_length: int
    has_tool_calls: bool
    tool_call_count: int
    has_content: bool
    metadata: dict = field(default_factory=dict)


class DebugInspector:
    """Inspect conversation messages for debugging."""

    def inspect(self, message: dict) -> MessageInspection:
        """Return a :class:`MessageInspection` for *message*."""
        role = message.get("role", "")
        content = message.get("content", "") or ""
        tool_calls = message.get("tool_calls", []) or []
        metadata = {
            k: v
            for k, v in message.items()
            if k not in ("role", "content", "tool_calls")
        }
        return MessageInspection(
            role=role,
            content_length=len(content) if isinstance(content, str) else 0,
            has_tool_calls=len(tool_calls) > 0,
            tool_call_count=len(tool_calls),
            has_content=bool(content),
            metadata=dict(metadata),
        )

    def inspect_batch(self, messages: list[dict]) -> list[MessageInspection]:
        """Inspect a list of messages."""
        return [self.inspect(m) for m in messages]

    def token_estimate(self, message: dict) -> int:
        """Rough token estimate: len(content) // 4."""
        content = message.get("content", "") or ""
        if not isinstance(content, str):
            return 0
        return len(content) // 4

    def timing_info(self, messages: list[dict]) -> list[dict]:
        """Add index and position info to each message."""
        total = len(messages)
        result: list[dict] = []
        for idx, msg in enumerate(messages):
            result.append({
                "index": idx,
                "role": msg.get("role", ""),
                "position": "first" if idx == 0 else ("last" if idx == total - 1 else "middle"),
                "content_length": len(msg.get("content", "") or ""),
            })
        return result
