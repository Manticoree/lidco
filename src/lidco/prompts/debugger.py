"""Q246: Prompt debugger — record turns, diff, token breakdown, and injection highlighting."""
from __future__ import annotations

from dataclasses import dataclass, field

# Rough token estimate: ~4 chars per token
_CHARS_PER_TOKEN = 4


@dataclass(frozen=True)
class _Turn:
    """Immutable record of a single prompt/response turn."""

    prompt: str
    response: str


class PromptDebugger:
    """Record and inspect prompt/response turns for debugging."""

    def __init__(self) -> None:
        self._turns: list[_Turn] = []

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_turn(self, prompt: str, response: str) -> None:
        """Append a new turn."""
        self._turns = [*self._turns, _Turn(prompt=prompt, response=response)]

    # ------------------------------------------------------------------
    # Diff
    # ------------------------------------------------------------------

    def diff(self, turn_a: int, turn_b: int) -> list[str]:
        """Simple line-level diff between prompts of two turns.

        Returns a list of diff lines prefixed with ``+``, ``-``, or `` ``.
        """
        if turn_a < 0 or turn_a >= len(self._turns):
            return [f"Turn {turn_a} out of range"]
        if turn_b < 0 or turn_b >= len(self._turns):
            return [f"Turn {turn_b} out of range"]

        lines_a = self._turns[turn_a].prompt.splitlines()
        lines_b = self._turns[turn_b].prompt.splitlines()

        result: list[str] = []
        max_len = max(len(lines_a), len(lines_b))
        for i in range(max_len):
            la = lines_a[i] if i < len(lines_a) else None
            lb = lines_b[i] if i < len(lines_b) else None
            if la == lb:
                result.append(f" {la}")
            else:
                if la is not None:
                    result.append(f"-{la}")
                if lb is not None:
                    result.append(f"+{lb}")
        return result

    # ------------------------------------------------------------------
    # Token breakdown
    # ------------------------------------------------------------------

    def token_breakdown(self, turn: int) -> dict:
        """Rough token estimate for a turn."""
        if turn < 0 or turn >= len(self._turns):
            return {}
        t = self._turns[turn]
        p_tokens = max(1, len(t.prompt) // _CHARS_PER_TOKEN)
        r_tokens = max(1, len(t.response) // _CHARS_PER_TOKEN)
        return {
            "prompt_tokens": p_tokens,
            "response_tokens": r_tokens,
            "total": p_tokens + r_tokens,
        }

    # ------------------------------------------------------------------
    # Show / history
    # ------------------------------------------------------------------

    def show_turn(self, turn: int) -> dict | None:
        """Return details of a single turn, or None if out of range."""
        if turn < 0 or turn >= len(self._turns):
            return None
        t = self._turns[turn]
        breakdown = self.token_breakdown(turn)
        return {
            "prompt": t.prompt,
            "response": t.response,
            "tokens": breakdown,
        }

    def history(self) -> list[dict]:
        """Return all turns as dicts."""
        result: list[dict] = []
        for i, t in enumerate(self._turns):
            bd = self.token_breakdown(i)
            result.append({
                "turn": i,
                "prompt_len": len(t.prompt),
                "response_len": len(t.response),
                "tokens": bd,
            })
        return result

    # ------------------------------------------------------------------
    # Injection highlighting
    # ------------------------------------------------------------------

    def highlight_injected(self, turn: int, markers: list[str]) -> str:
        """Wrap occurrences of *markers* in the prompt with ``[INJECTED: ...]``."""
        if turn < 0 or turn >= len(self._turns):
            return ""
        text = self._turns[turn].prompt
        for marker in markers:
            text = text.replace(marker, f"[INJECTED: {marker}]")
        return text
