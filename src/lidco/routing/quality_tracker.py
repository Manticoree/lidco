"""Track response quality per model over time."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class QualityRecord:
    """A single quality observation."""

    model: str
    score: float
    task_type: str = "general"
    timestamp: float = field(default_factory=time.time)


class QualityTracker:
    """Maintain a sliding window of quality records per model."""

    def __init__(self, window_size: int = 100) -> None:
        self._window_size = window_size
        self._records: list[QualityRecord] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        model: str,
        score: float,
        task_type: str = "general",
    ) -> QualityRecord:
        """Record a quality observation and return it."""
        rec = QualityRecord(model=model, score=score, task_type=task_type)
        self._records = [*self._records, rec]
        # trim to window
        if len(self._records) > self._window_size:
            self._records = list(self._records[-self._window_size :])
        return rec

    def average(self, model: str, task_type: str | None = None) -> float | None:
        """Return average quality score for *model*, optionally filtered by *task_type*."""
        recs = [
            r
            for r in self._records
            if r.model == model and (task_type is None or r.task_type == task_type)
        ]
        if not recs:
            return None
        return sum(r.score for r in recs) / len(recs)

    def compare(self, model_a: str, model_b: str) -> dict:
        """Compare two models. Returns winner and scores."""
        avg_a = self.average(model_a)
        avg_b = self.average(model_b)
        if avg_a is None and avg_b is None:
            return {"winner": None, "model_a": None, "model_b": None}
        if avg_a is None:
            return {"winner": model_b, "model_a": None, "model_b": avg_b}
        if avg_b is None:
            return {"winner": model_a, "model_a": avg_a, "model_b": None}
        winner = model_a if avg_a >= avg_b else model_b
        return {"winner": winner, "model_a": avg_a, "model_b": avg_b}

    def detect_regression(self, model: str, threshold: float = 0.1) -> bool:
        """Return True if recent avg is below overall avg by *threshold*."""
        recs = [r for r in self._records if r.model == model]
        if len(recs) < 4:
            return False
        overall = sum(r.score for r in recs) / len(recs)
        half = len(recs) // 2
        recent = recs[half:]
        recent_avg = sum(r.score for r in recent) / len(recent)
        return (overall - recent_avg) >= threshold

    def summary(self) -> dict:
        """Per-model statistics."""
        models: dict[str, list[float]] = {}
        for r in self._records:
            models.setdefault(r.model, []).append(r.score)
        result: dict[str, dict] = {}
        for model, scores in models.items():
            result[model] = {
                "count": len(scores),
                "avg": round(sum(scores) / len(scores), 4),
                "min": round(min(scores), 4),
                "max": round(max(scores), 4),
            }
        return result

    def records(self, model: str | None = None) -> list[QualityRecord]:
        """Return records, optionally filtered by *model*."""
        if model is None:
            return list(self._records)
        return [r for r in self._records if r.model == model]
