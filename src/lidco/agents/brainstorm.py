"""BrainstormAgent — explore alternatives before planning."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class BrainstormResult:
    alternatives: list[str]
    risks: list[str]
    clarifying_questions: list[str]
    recommended_approach: str


class BrainstormAgent:
    """Spawn a brainstorm sub-agent before the planner to explore options."""

    def __init__(self, llm_fn: Callable[[str], str] | None = None) -> None:
        """llm_fn(prompt) -> str"""
        self._llm_fn = llm_fn

    def brainstorm(self, goal: str, context: str = "") -> BrainstormResult:
        """Generate alternatives, risks, questions, and a recommendation."""
        if self._llm_fn is None:
            return BrainstormResult(
                alternatives=[f"Direct implementation of: {goal}"],
                risks=["Scope may be underspecified"],
                clarifying_questions=[f"What is the expected outcome of: {goal}?"],
                recommended_approach=f"Implement {goal} directly.",
            )

        prompt = _build_prompt(goal, context)
        try:
            raw = self._llm_fn(prompt)
            return _parse_response(raw, goal)
        except Exception:
            return BrainstormResult(
                alternatives=[goal],
                risks=[],
                clarifying_questions=[],
                recommended_approach=goal,
            )


def _build_prompt(goal: str, context: str) -> str:
    return (
        f"Brainstorm approaches for: {goal}\n\n"
        f"Context: {context[:500]}\n\n"
        "Return JSON with keys: alternatives (list), risks (list), "
        "clarifying_questions (list), recommended_approach (string)"
    )


def _parse_response(raw: str, fallback_goal: str) -> BrainstormResult:
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return BrainstormResult(alternatives=[fallback_goal], risks=[], clarifying_questions=[], recommended_approach=fallback_goal)
    try:
        data = json.loads(raw[start:end])
        return BrainstormResult(
            alternatives=data.get("alternatives", [fallback_goal]),
            risks=data.get("risks", []),
            clarifying_questions=data.get("clarifying_questions", []),
            recommended_approach=data.get("recommended_approach", fallback_goal),
        )
    except Exception:
        return BrainstormResult(alternatives=[fallback_goal], risks=[], clarifying_questions=[], recommended_approach=fallback_goal)
