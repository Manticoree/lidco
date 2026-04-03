"""Turn-level conversation analysis (Q248)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TurnAnalysis:
    """Analysis result for a single conversation turn."""

    index: int
    role: str
    token_estimate: int
    has_tool_calls: bool
    files_mentioned: list[str] = field(default_factory=list)
    score: float = 0.0


_FILE_RE = re.compile(r"[\w./\\-]+\.\w{1,10}")


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(1, len(text) // 4) if text else 0


def _extract_files(text: str) -> list[str]:
    """Extract file-path-like strings from *text*."""
    if not text:
        return []
    matches = _FILE_RE.findall(text)
    seen: set[str] = set()
    result: list[str] = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result


def _score_turn(msg: dict) -> float:
    """Heuristic quality score 0.0–1.0 for a turn."""
    content = msg.get("content") or ""
    role = msg.get("role", "")
    if not content:
        return 0.0
    base = min(len(content) / 500.0, 1.0)
    if role == "assistant":
        base *= 1.0
    elif role == "user":
        base *= 0.8
    else:
        base *= 0.5
    if msg.get("tool_calls"):
        base = min(base + 0.2, 1.0)
    return round(base, 3)


class TurnAnalyzer:
    """Analyze individual turns of a conversation."""

    def __init__(self, messages: list[dict]) -> None:
        self._messages = list(messages)

    def analyze_turn(self, index: int) -> TurnAnalysis:
        """Analyze a single turn by *index*."""
        if index < 0 or index >= len(self._messages):
            raise IndexError(f"Turn index {index} out of range")
        msg = self._messages[index]
        content = msg.get("content") or ""
        role = msg.get("role", "unknown")
        tokens = _estimate_tokens(content)
        has_tools = bool(msg.get("tool_calls"))
        files = _extract_files(content)
        score = _score_turn(msg)
        return TurnAnalysis(
            index=index,
            role=role,
            token_estimate=tokens,
            has_tool_calls=has_tools,
            files_mentioned=files,
            score=score,
        )

    def analyze_all(self) -> list[TurnAnalysis]:
        """Analyze every turn."""
        return [self.analyze_turn(i) for i in range(len(self._messages))]

    def token_deltas(self) -> list[int]:
        """Token change per turn (first turn delta is its own estimate)."""
        analyses = self.analyze_all()
        if not analyses:
            return []
        deltas = [analyses[0].token_estimate]
        for prev, cur in zip(analyses, analyses[1:]):
            deltas.append(cur.token_estimate - prev.token_estimate)
        return deltas

    def summary(self) -> str:
        """Human-readable summary of the conversation turns."""
        analyses = self.analyze_all()
        if not analyses:
            return "No turns to analyze."
        total_tokens = sum(a.token_estimate for a in analyses)
        tool_turns = sum(1 for a in analyses if a.has_tool_calls)
        roles = {}
        for a in analyses:
            roles[a.role] = roles.get(a.role, 0) + 1
        role_parts = ", ".join(f"{r}: {c}" for r, c in sorted(roles.items()))
        avg_score = sum(a.score for a in analyses) / len(analyses)
        return (
            f"Turns: {len(analyses)} | Tokens: ~{total_tokens} | "
            f"Tool turns: {tool_turns} | Roles: {role_parts} | "
            f"Avg score: {avg_score:.2f}"
        )
