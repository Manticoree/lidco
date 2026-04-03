"""Conversation success prediction (Q248)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Prediction:
    """Success prediction result."""

    likelihood: float
    factors: list[str] = field(default_factory=list)
    recommendation: str = ""


class SuccessPredictor:
    """Predict conversation success from message history."""

    def __init__(self, messages: list[dict]) -> None:
        self._messages = list(messages)

    def error_rate(self) -> float:
        """Fraction of turns with errors or empty content."""
        if not self._messages:
            return 0.0
        errors = 0
        for msg in self._messages:
            content = (msg.get("content") or "").strip()
            if not content:
                errors += 1
            elif content.lower().startswith("error"):
                errors += 1
        return errors / len(self._messages)

    def tool_diversity(self) -> float:
        """Unique tools / total tool calls.  Returns 0.0 if no calls."""
        total = 0
        unique: set[str] = set()
        for msg in self._messages:
            for tc in (msg.get("tool_calls") or []):
                name = tc if isinstance(tc, str) else (
                    tc.get("name", "") if isinstance(tc, dict) else ""
                )
                if name:
                    unique.add(name)
                    total += 1
        if total == 0:
            return 0.0
        return len(unique) / total

    def conversation_health(self) -> dict:
        """Return health metrics dict."""
        er = self.error_rate()
        div = self.tool_diversity()
        length = len(self._messages)
        if length == 0:
            return {"length": 0, "error_rate": 0.0, "diversity": 0.0, "score": 0.0}
        # composite score: lower error rate + higher diversity + reasonable length
        length_score = min(length / 20.0, 1.0)
        score = round((1.0 - er) * 0.5 + div * 0.3 + length_score * 0.2, 3)
        return {
            "length": length,
            "error_rate": round(er, 3),
            "diversity": round(div, 3),
            "score": score,
        }

    def predict(self) -> Prediction:
        """Predict likelihood of successful conversation outcome."""
        health = self.conversation_health()
        factors: list[str] = []
        likelihood = health["score"]

        if health["error_rate"] > 0.3:
            factors.append("High error rate")
            likelihood = max(likelihood - 0.1, 0.0)
        elif health["error_rate"] == 0.0 and health["length"] > 0:
            factors.append("No errors detected")

        if health["diversity"] > 0.5:
            factors.append("Good tool diversity")
        elif health["diversity"] == 0.0 and health["length"] > 0:
            factors.append("No tool usage")

        if health["length"] < 3:
            factors.append("Conversation too short for reliable prediction")

        if health["length"] > 50:
            factors.append("Long conversation may indicate complexity")

        likelihood = round(min(max(likelihood, 0.0), 1.0), 3)

        if likelihood >= 0.7:
            rec = "Conversation is on track."
        elif likelihood >= 0.4:
            rec = "Consider refining the approach or breaking the task down."
        else:
            rec = "High risk of failure. Review errors and retry with a fresh approach."

        return Prediction(
            likelihood=likelihood,
            factors=factors,
            recommendation=rec,
        )
