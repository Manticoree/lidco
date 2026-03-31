"""Model Downgrade Optimizer — auto-switch to cheaper models for simple tasks."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelTier:
    """A model tier with cost information."""

    name: str
    cost_per_1k_input: float
    cost_per_1k_output: float
    quality_score: float  # 0.0–1.0, relative quality rating
    max_tokens: int = 128000


@dataclass(frozen=True)
class TaskClassification:
    """Classification of a task's complexity."""

    complexity: str  # "simple" | "moderate" | "complex"
    confidence: float  # 0.0–1.0
    reason: str = ""


@dataclass
class QualityRecord:
    """Tracks quality for a model on a task type."""

    model_name: str
    task_type: str
    successes: int = 0
    failures: int = 0
    total_cost: float = 0.0
    total_tokens: int = 0

    @property
    def success_rate(self) -> float:
        total = self.successes + self.failures
        return self.successes / total if total > 0 else 0.0


@dataclass(frozen=True)
class ModelRecommendation:
    """A model recommendation from the optimizer."""

    recommended_model: str
    original_model: str
    task_complexity: str
    estimated_savings_pct: float
    quality_confidence: float
    reason: str


class ModelOptimizer:
    """Auto-switch to cheaper model for simple tasks with A/B quality tracking.

    Classifies tasks by complexity and recommends cheaper models when quality
    is expected to remain acceptable.
    """

    SIMPLE_INDICATORS = frozenset({
        "format", "list", "summarize", "translate", "extract", "convert",
        "count", "sort", "filter", "rename", "describe", "define",
    })

    COMPLEX_INDICATORS = frozenset({
        "architect", "refactor", "design", "optimize", "debug", "security",
        "review", "analyze", "implement", "migrate", "integrate",
    })

    def __init__(
        self,
        tiers: list[ModelTier] | None = None,
        min_quality_threshold: float = 0.7,
    ) -> None:
        self._tiers: dict[str, ModelTier] = {}
        self._quality_records: dict[str, QualityRecord] = {}
        self._min_quality = min_quality_threshold
        self._recommendations: list[ModelRecommendation] = []
        if tiers:
            for tier in tiers:
                self._tiers[tier.name] = tier

    # -- Tier management --

    def add_tier(self, tier: ModelTier) -> None:
        """Register a model tier."""
        self._tiers[tier.name] = tier

    def remove_tier(self, name: str) -> bool:
        """Remove a tier."""
        if name in self._tiers:
            del self._tiers[name]
            return True
        return False

    def list_tiers(self) -> list[ModelTier]:
        """Return all tiers sorted by cost (cheapest first)."""
        return sorted(self._tiers.values(), key=lambda t: t.cost_per_1k_input)

    def get_tier(self, name: str) -> ModelTier | None:
        """Get a tier by name."""
        return self._tiers.get(name)

    # -- Task classification --

    def classify_task(self, task_description: str) -> TaskClassification:
        """Classify a task as simple, moderate, or complex based on keywords."""
        words = set(task_description.lower().split())
        simple_hits = len(words & self.SIMPLE_INDICATORS)
        complex_hits = len(words & self.COMPLEX_INDICATORS)

        if complex_hits > simple_hits:
            confidence = min(1.0, 0.5 + complex_hits * 0.15)
            return TaskClassification("complex", confidence, f"Complex keywords: {complex_hits}")
        elif simple_hits > complex_hits:
            confidence = min(1.0, 0.5 + simple_hits * 0.15)
            return TaskClassification("simple", confidence, f"Simple keywords: {simple_hits}")
        else:
            return TaskClassification("moderate", 0.5, "Mixed or no clear indicators")

    # -- Recommendation --

    def recommend_model(
        self,
        task_description: str,
        current_model: str,
    ) -> ModelRecommendation:
        """Recommend a model for the given task.

        May suggest a cheaper model if the task is simple and quality records
        support it.
        """
        classification = self.classify_task(task_description)
        current_tier = self._tiers.get(current_model)
        tiers_sorted = self.list_tiers()

        if not tiers_sorted or current_tier is None:
            rec = ModelRecommendation(
                recommended_model=current_model,
                original_model=current_model,
                task_complexity=classification.complexity,
                estimated_savings_pct=0.0,
                quality_confidence=0.5,
                reason="No tier data available; keeping current model.",
            )
            self._recommendations.append(rec)
            return rec

        if classification.complexity == "simple":
            # Try cheapest model with acceptable quality
            for tier in tiers_sorted:
                if tier.cost_per_1k_input < current_tier.cost_per_1k_input:
                    qr = self._get_quality(tier.name, "simple")
                    if qr.success_rate >= self._min_quality or (qr.successes + qr.failures) < 3:
                        savings = 1.0 - (tier.cost_per_1k_input / current_tier.cost_per_1k_input)
                        rec = ModelRecommendation(
                            recommended_model=tier.name,
                            original_model=current_model,
                            task_complexity="simple",
                            estimated_savings_pct=savings * 100,
                            quality_confidence=qr.success_rate if (qr.successes + qr.failures) >= 3 else tier.quality_score,
                            reason=f"Simple task; {tier.name} saves {savings*100:.0f}%.",
                        )
                        self._recommendations.append(rec)
                        return rec

        # Default: keep current model
        rec = ModelRecommendation(
            recommended_model=current_model,
            original_model=current_model,
            task_complexity=classification.complexity,
            estimated_savings_pct=0.0,
            quality_confidence=current_tier.quality_score,
            reason=f"Task is {classification.complexity}; keeping {current_model}.",
        )
        self._recommendations.append(rec)
        return rec

    # -- Quality tracking --

    def record_quality(self, model_name: str, task_type: str, success: bool, cost: float = 0.0, tokens: int = 0) -> None:
        """Record quality outcome for A/B tracking."""
        key = f"{model_name}:{task_type}"
        if key not in self._quality_records:
            self._quality_records[key] = QualityRecord(model_name=model_name, task_type=task_type)
        qr = self._quality_records[key]
        if success:
            qr.successes += 1
        else:
            qr.failures += 1
        qr.total_cost += cost
        qr.total_tokens += tokens

    def get_quality(self, model_name: str, task_type: str) -> QualityRecord | None:
        """Get quality record for a model+task combo."""
        return self._quality_records.get(f"{model_name}:{task_type}")

    def _get_quality(self, model_name: str, task_type: str) -> QualityRecord:
        key = f"{model_name}:{task_type}"
        if key not in self._quality_records:
            self._quality_records[key] = QualityRecord(model_name=model_name, task_type=task_type)
        return self._quality_records[key]

    @property
    def recommendations(self) -> list[ModelRecommendation]:
        """All past recommendations."""
        return list(self._recommendations)

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [f"Model tiers: {len(self._tiers)}"]
        for tier in self.list_tiers():
            lines.append(f"  {tier.name}: ${tier.cost_per_1k_input}/1k in, quality={tier.quality_score:.2f}")
        lines.append(f"Quality records: {len(self._quality_records)}")
        for key, qr in self._quality_records.items():
            lines.append(f"  {key}: {qr.successes}/{qr.successes + qr.failures} success rate={qr.success_rate:.2f}")
        lines.append(f"Recommendations made: {len(self._recommendations)}")
        return "\n".join(lines)
