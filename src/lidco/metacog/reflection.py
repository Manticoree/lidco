"""ReflectionEngine — generate self-assessments after responses."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Reflection:
    """Self-assessment of a response."""

    response_id: str
    timestamp: float = field(default_factory=time.time)
    what_worked: list[str] = field(default_factory=list)
    what_didnt: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    confidence: float = 0.5
    quality_score: float = 0.5


class ReflectionEngine:
    """Generate and store self-reflections on responses."""

    def __init__(self, max_history: int = 100) -> None:
        self._history: list[Reflection] = []
        self._max_history = max_history

    def reflect(
        self,
        response_id: str,
        response_text: str,
        task_type: str = "general",
        tools_used: list[str] | None = None,
    ) -> Reflection:
        """Generate a reflection on a response."""
        tools_used = tools_used or []

        what_worked = []
        what_didnt = []
        improvements = []

        # Heuristic assessments
        if len(response_text) > 50:
            what_worked.append("Provided substantive response")
        else:
            what_didnt.append("Response may be too brief")
            improvements.append("Provide more detail")

        if tools_used:
            what_worked.append(f"Used {len(tools_used)} tool(s)")
        elif task_type in ("code", "debug", "search"):
            what_didnt.append("No tools used for code task")
            improvements.append("Consider using relevant tools")

        if task_type == "explanation" and len(response_text) > 200:
            what_worked.append("Detailed explanation provided")

        quality = self._estimate_quality(response_text, task_type, tools_used)
        confidence = min(quality + 0.1, 1.0)

        ref = Reflection(
            response_id=response_id,
            what_worked=what_worked,
            what_didnt=what_didnt,
            improvements=improvements,
            confidence=round(confidence, 3),
            quality_score=round(quality, 3),
        )
        self._history.append(ref)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        return ref

    def history(self) -> list[Reflection]:
        return list(self._history)

    def average_quality(self) -> float:
        if not self._history:
            return 0.0
        return round(sum(r.quality_score for r in self._history) / len(self._history), 3)

    def improvement_summary(self) -> list[str]:
        """Aggregate unique improvement suggestions."""
        seen: set[str] = set()
        result: list[str] = []
        for r in self._history:
            for imp in r.improvements:
                if imp not in seen:
                    seen.add(imp)
                    result.append(imp)
        return result

    def _estimate_quality(
        self, text: str, task_type: str, tools: list[str]
    ) -> float:
        score = 0.3
        if len(text) > 100:
            score += 0.2
        if len(text) > 300:
            score += 0.1
        if tools:
            score += 0.2
        if task_type in ("code", "debug") and any("edit" in t.lower() or "write" in t.lower() for t in tools):
            score += 0.1
        return min(score, 1.0)
