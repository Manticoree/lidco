"""ConfidenceCalibrator — track prediction accuracy and calibrate confidence."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass
class Prediction:
    """A prediction with confidence and actual outcome."""

    prediction_id: str
    predicted: str
    confidence: float  # 0-1
    actual: str | None = None
    correct: bool | None = None


class ConfidenceCalibrator:
    """Track and calibrate confidence scores against actual outcomes."""

    def __init__(self) -> None:
        self._predictions: list[Prediction] = []
        self._bucket_size: int = 10  # for calibration curve

    def record_prediction(
        self, prediction_id: str, predicted: str, confidence: float
    ) -> Prediction:
        """Record a new prediction."""
        p = Prediction(
            prediction_id=prediction_id,
            predicted=predicted,
            confidence=max(0.0, min(confidence, 1.0)),
        )
        self._predictions.append(p)
        return p

    def record_outcome(self, prediction_id: str, actual: str) -> Prediction | None:
        """Record the actual outcome for a prediction."""
        for p in self._predictions:
            if p.prediction_id == prediction_id:
                p.actual = actual
                p.correct = p.predicted == actual
                return p
        return None

    def accuracy(self) -> float:
        """Overall accuracy of resolved predictions."""
        resolved = [p for p in self._predictions if p.correct is not None]
        if not resolved:
            return 0.0
        correct = sum(1 for p in resolved if p.correct)
        return round(correct / len(resolved), 3)

    def brier_score(self) -> float:
        """Brier score — lower is better. Measures calibration quality."""
        resolved = [p for p in self._predictions if p.correct is not None]
        if not resolved:
            return 0.0
        total = sum((p.confidence - (1.0 if p.correct else 0.0)) ** 2 for p in resolved)
        return round(total / len(resolved), 4)

    def is_overconfident(self, threshold: float = 0.1) -> bool:
        """Detect if systematically overconfident."""
        resolved = [p for p in self._predictions if p.correct is not None]
        if len(resolved) < 5:
            return False
        avg_conf = sum(p.confidence for p in resolved) / len(resolved)
        acc = self.accuracy()
        return (avg_conf - acc) > threshold

    def calibration_curve(self) -> list[dict]:
        """Return calibration data: buckets of (avg_confidence, actual_accuracy)."""
        resolved = [p for p in self._predictions if p.correct is not None]
        if not resolved:
            return []
        sorted_preds = sorted(resolved, key=lambda p: p.confidence)
        buckets = []
        for i in range(0, len(sorted_preds), self._bucket_size):
            chunk = sorted_preds[i:i + self._bucket_size]
            avg_conf = sum(p.confidence for p in chunk) / len(chunk)
            avg_acc = sum(1 for p in chunk if p.correct) / len(chunk)
            buckets.append({
                "avg_confidence": round(avg_conf, 3),
                "actual_accuracy": round(avg_acc, 3),
                "count": len(chunk),
            })
        return buckets

    def predictions(self) -> list[Prediction]:
        return list(self._predictions)

    def summary(self) -> dict:
        """Summary statistics."""
        resolved = [p for p in self._predictions if p.correct is not None]
        return {
            "total_predictions": len(self._predictions),
            "resolved": len(resolved),
            "accuracy": self.accuracy(),
            "brier_score": self.brier_score(),
            "overconfident": self.is_overconfident(),
        }
