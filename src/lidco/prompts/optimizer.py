"""Q246: Prompt optimizer — A/B testing and variant selection for prompts."""
from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field


@dataclass
class PromptVariant:
    """A single prompt variant with scoring metadata."""

    id: str
    prompt: str
    score: float = 0.0
    uses: int = 0
    _scores: list[float] = field(default_factory=list, repr=False)


class PromptOptimizer:
    """Manage prompt variants, record scores, and select the best one."""

    def __init__(self) -> None:
        self._variants: dict[str, PromptVariant] = {}

    # ------------------------------------------------------------------
    # Mutation-free helpers
    # ------------------------------------------------------------------

    def add_variant(self, prompt: str) -> str:
        """Add a new variant and return its id."""
        vid = uuid.uuid4().hex[:8]
        variant = PromptVariant(id=vid, prompt=prompt)
        self._variants = {**self._variants, vid: variant}
        return vid

    def record_score(self, variant_id: str, score: float) -> None:
        """Record a score for a variant (updates average)."""
        old = self._variants.get(variant_id)
        if old is None:
            return
        new_scores = [*old._scores, score]
        avg = sum(new_scores) / len(new_scores)
        updated = PromptVariant(
            id=old.id,
            prompt=old.prompt,
            score=avg,
            uses=old.uses + 1,
            _scores=new_scores,
        )
        self._variants = {**self._variants, variant_id: updated}

    def best(self) -> PromptVariant | None:
        """Return the variant with the highest average score, or None."""
        if not self._variants:
            return None
        scored = [v for v in self._variants.values() if v.uses > 0]
        if not scored:
            return None
        return max(scored, key=lambda v: v.score)

    def select(self) -> PromptVariant | None:
        """Weighted random selection by score (uniform if no scores yet)."""
        variants = list(self._variants.values())
        if not variants:
            return None
        scored = [v for v in variants if v.uses > 0]
        if not scored:
            return random.choice(variants)
        weights = [max(v.score, 0.01) for v in scored]
        total = sum(weights)
        r = random.random() * total
        cumulative = 0.0
        for v, w in zip(scored, weights):
            cumulative += w
            if r <= cumulative:
                return v
        return scored[-1]

    def list_variants(self) -> list[PromptVariant]:
        """Return all variants."""
        return list(self._variants.values())

    def remove_variant(self, variant_id: str) -> bool:
        """Remove a variant by id. Returns True if found."""
        if variant_id not in self._variants:
            return False
        self._variants = {k: v for k, v in self._variants.items() if k != variant_id}
        return True

    def stats(self) -> dict:
        """Return summary statistics."""
        variants = list(self._variants.values())
        scored = [v for v in variants if v.uses > 0]
        return {
            "total_variants": len(variants),
            "scored_variants": len(scored),
            "best_score": max((v.score for v in scored), default=0.0),
            "total_uses": sum(v.uses for v in variants),
        }
