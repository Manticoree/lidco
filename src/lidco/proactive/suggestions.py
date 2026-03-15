"""Next-action suggestion engine — Task 413."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class Suggestion:
    """A next-action suggestion."""

    text: str
    command_hint: str
    confidence: float  # 0.0–1.0


_SYSTEM_PROMPT = (
    "You are a helpful developer assistant. Based on the agent's last response and "
    "project context, suggest 3 short, concrete next actions the developer should take. "
    "Format EXACTLY as:\n"
    "1. <action> [hint: /command]\n"
    "2. <action> [hint: /command]\n"
    "3. <action> [hint: /command]\n"
    "Keep each action under 15 words. If no command fits, omit the hint."
)


class SuggestionEngine:
    """Generate next-action suggestions from an agent's last response."""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def suggest(self, last_response: str, context: str = "") -> list[Suggestion]:
        """Return up to 3 Suggestion items using a fast LLM call."""
        if not last_response.strip():
            return []

        prompt = (
            f"Last agent response:\n{last_response[:1000]}\n\n"
            f"Project context:\n{context[:500]}\n\n"
            "Suggest 3 next actions."
        )

        try:
            raw = await self._call_llm(prompt)
        except Exception:
            return []

        return _parse_suggestions(raw)

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    async def _call_llm(self, prompt: str) -> str:
        """Make a fast LLM call via the session's orchestrator."""
        if self._session is None:
            return ""
        orch = getattr(self._session, "orchestrator", None)
        if orch is None:
            return ""
        # Use a fast/cheap model via the routing role "haiku"
        llm = getattr(self._session, "_llm", None) or getattr(self._session, "llm", None)
        if llm is None:
            return ""

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        resp = await llm.acompletion(
            messages=messages,
            max_tokens=200,
            temperature=0.4,
        )
        if hasattr(resp, "choices") and resp.choices:
            return resp.choices[0].message.content or ""
        return str(resp)


def _parse_suggestions(raw: str) -> list[Suggestion]:
    """Parse numbered suggestion lines into Suggestion objects."""
    import re

    results: list[Suggestion] = []
    for line in raw.splitlines():
        line = line.strip()
        m = re.match(r"^\d+\.\s+(.+)$", line)
        if not m:
            continue
        content = m.group(1).strip()
        # Extract optional [hint: /cmd]
        hint_match = re.search(r"\[hint:\s*([^\]]+)\]", content)
        hint = ""
        if hint_match:
            hint = hint_match.group(1)
            content = content[: hint_match.start()].strip()
        # Confidence heuristic: 0.9 for 1st, 0.75 for 2nd, 0.6 for 3rd
        confidence = max(0.5, 0.95 - len(results) * 0.15)
        results.append(Suggestion(text=content, command_hint=hint, confidence=round(confidence, 2)))
        if len(results) >= 3:
            break

    return results
