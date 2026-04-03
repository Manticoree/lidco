"""EnsembleRunner — run multiple models and aggregate results."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EnsembleResult:
    """Aggregated result from ensemble execution."""

    responses: list[dict]
    winner: str
    method: str


class EnsembleRunner:
    """Run a prompt against multiple models and aggregate responses."""

    def __init__(self) -> None:
        self._models: list[dict] = []

    def add_model(self, name: str, weight: float = 1.0) -> None:
        self._models = [*self._models, {"name": name, "weight": weight}]

    def run(self, prompt: str) -> EnsembleResult:
        """Simulate ensemble execution; returns EnsembleResult."""
        responses = [
            {"model": m["name"], "text": f"Response from {m['name']}"}
            for m in self._models
        ]
        winner = self.vote(responses)
        return EnsembleResult(responses=responses, winner=winner, method="vote")

    def vote(self, responses: list[dict]) -> str:
        """Simple majority vote on response text; ties go to first."""
        if not responses:
            return ""
        counts: Counter[str] = Counter()
        for r in responses:
            counts[r.get("text", "")] += 1
        # most_common returns list of (text, count); take the first
        best_text = counts.most_common(1)[0][0]
        # Return the model name of the first response with that text
        for r in responses:
            if r.get("text", "") == best_text:
                return r.get("model", "")
        return ""

    def merge(self, responses: list[dict]) -> str:
        """Concatenate unique response texts."""
        seen: set[str] = set()
        parts: list[str] = []
        for r in responses:
            text = r.get("text", "")
            if text and text not in seen:
                seen = {*seen, text}
                parts = [*parts, text]
        return "\n".join(parts)

    def list_models(self) -> list[dict]:
        return list(self._models)
