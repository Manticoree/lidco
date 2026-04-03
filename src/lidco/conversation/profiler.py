"""Conversation profiler for cost, hotspot, and waste analysis."""
from __future__ import annotations


class ConversationProfiler:
    """Profile a conversation for token usage, hotspots, and waste."""

    def __init__(self, messages: list[dict]) -> None:
        self._messages: list[dict] = list(messages)

    def _token_count(self, message: dict) -> int:
        content = message.get("content", "") or ""
        if not isinstance(content, str):
            return 0
        return len(content) // 4

    def cost_per_turn(self) -> list[dict]:
        """Return per-turn cost info with cumulative token counts."""
        result: list[dict] = []
        cumulative = 0
        for idx, msg in enumerate(self._messages):
            tokens = self._token_count(msg)
            cumulative = cumulative + tokens
            result.append({
                "turn": idx,
                "role": msg.get("role", ""),
                "tokens": tokens,
                "cumulative": cumulative,
            })
        return result

    def hotspots(self, threshold: int = 1000) -> list[dict]:
        """Return turns whose token count exceeds *threshold*."""
        result: list[dict] = []
        for idx, msg in enumerate(self._messages):
            tokens = self._token_count(msg)
            if tokens >= threshold:
                result.append({
                    "turn": idx,
                    "role": msg.get("role", ""),
                    "tokens": tokens,
                })
        return result

    def waste_detection(self) -> list[dict]:
        """Identify empty, near-empty, or repeated-content turns."""
        waste: list[dict] = []
        seen_contents: dict[str, int] = {}
        for idx, msg in enumerate(self._messages):
            content = msg.get("content", "") or ""
            if not isinstance(content, str):
                content = ""
            reason: str | None = None
            if len(content) == 0:
                reason = "empty"
            elif len(content) < 5:
                reason = "near-empty"
            elif content in seen_contents:
                reason = f"duplicate of turn {seen_contents[content]}"
            if reason is not None:
                waste.append({
                    "turn": idx,
                    "role": msg.get("role", ""),
                    "reason": reason,
                })
            if content:
                seen_contents[content] = idx
        return waste

    def total_tokens(self) -> int:
        """Total estimated tokens across all messages."""
        return sum(self._token_count(m) for m in self._messages)

    def summary(self) -> str:
        """Human-readable profiling summary."""
        total = self.total_tokens()
        turns = len(self._messages)
        hot = self.hotspots()
        w = self.waste_detection()
        lines = [
            f"Turns: {turns}",
            f"Total tokens: {total}",
            f"Hotspots: {len(hot)}",
            f"Waste turns: {len(w)}",
        ]
        return "\n".join(lines)
