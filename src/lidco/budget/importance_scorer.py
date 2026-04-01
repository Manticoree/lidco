"""Score message importance for eviction decisions."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScoredMessage:
    """A message annotated with importance score."""

    index: int
    role: str
    importance: float = 0.5
    reasons: tuple[str, ...] = ()
    pinned: bool = False
    age_turns: int = 0


class ImportanceScorer:
    """Score messages for eviction priority."""

    def __init__(self, decay_per_turn: float = 0.02) -> None:
        self._decay = decay_per_turn

    def score(
        self,
        message: dict,
        index: int,
        current_turn: int,
        pinned_indices: set[int] | None = None,
    ) -> ScoredMessage:
        """Score a single message based on role, content, and age."""
        pinned_set = pinned_indices or set()
        role = message.get("role", "")
        content = message.get("content", "") or ""
        reasons: list[str] = []
        is_pinned = index in pinned_set

        # Base score by role / content
        if role == "system":
            base = 1.0
            reasons.append("system message")
        elif is_pinned:
            base = 1.0
            reasons.append("pinned")
        elif "```" in content:
            base = 0.8
            reasons.append("contains code block")
        elif any(kw in content.lower() for kw in ("error", "traceback", "exception")):
            base = 0.9
            reasons.append("contains error/traceback")
        elif role == "user":
            base = 0.7
            reasons.append("user question")
        elif role == "assistant" and len(content) < 50:
            base = 0.2
            reasons.append("short assistant reply")
        elif role == "tool":
            base = 0.4
            reasons.append("tool result")
        else:
            base = 0.5
            reasons.append("default")

        # Age decay
        age = max(0, current_turn - index)
        decayed = base - self._decay * age
        score = max(0.0, decayed)

        # System and pinned never decay
        if role == "system" or is_pinned:
            score = 1.0

        return ScoredMessage(
            index=index,
            role=role,
            importance=round(score, 4),
            reasons=tuple(reasons),
            pinned=is_pinned,
            age_turns=age,
        )

    def score_all(
        self,
        messages: list[dict],
        current_turn: int,
        pinned_indices: set[int] | None = None,
    ) -> list[ScoredMessage]:
        """Score every message in a conversation."""
        return [
            self.score(msg, i, current_turn, pinned_indices)
            for i, msg in enumerate(messages)
        ]

    def rank(self, scored: list[ScoredMessage]) -> list[ScoredMessage]:
        """Sort by importance ascending (lowest first = evict first)."""
        return sorted(scored, key=lambda s: s.importance)

    def summary(self, scored: list[ScoredMessage]) -> str:
        """Human-readable summary of scored messages."""
        lines = [f"Scored {len(scored)} messages:"]
        for s in scored[:20]:
            pin = " [PINNED]" if s.pinned else ""
            lines.append(
                f"  [{s.index}] {s.role} importance={s.importance:.2f} "
                f"age={s.age_turns}{pin} ({', '.join(s.reasons)})"
            )
        if len(scored) > 20:
            lines.append(f"  ... and {len(scored) - 20} more")
        return "\n".join(lines)
