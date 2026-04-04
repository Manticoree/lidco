"""ArgumentEvaluator — score arguments on evidence, logic, novelty, persuasiveness."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ArgumentScore:
    """Scored assessment of an argument."""

    evidence_quality: float = 0.0  # 0-1
    logical_consistency: float = 0.0  # 0-1
    novelty: float = 0.0  # 0-1
    persuasiveness: float = 0.0  # 0-1
    overall: float = 0.0  # weighted average
    feedback: str = ""


class ArgumentEvaluator:
    """Evaluate debate arguments across multiple dimensions."""

    def __init__(
        self,
        weights: dict[str, float] | None = None,
    ) -> None:
        self._weights = weights or {
            "evidence_quality": 0.3,
            "logical_consistency": 0.3,
            "novelty": 0.2,
            "persuasiveness": 0.2,
        }
        self._scores: list[tuple[str, ArgumentScore]] = []

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)

    def evaluate(
        self,
        agent_id: str,
        content: str,
        evidence: list[str] | None = None,
        prior_arguments: list[str] | None = None,
    ) -> ArgumentScore:
        """Evaluate an argument and return a score."""
        evidence = evidence or []
        prior_arguments = prior_arguments or []

        ev_quality = min(len(evidence) * 0.25, 1.0)
        logic = self._assess_logic(content)
        novelty = self._assess_novelty(content, prior_arguments)
        persuasiveness = self._assess_persuasiveness(content, evidence)

        overall = (
            ev_quality * self._weights.get("evidence_quality", 0.25)
            + logic * self._weights.get("logical_consistency", 0.25)
            + novelty * self._weights.get("novelty", 0.25)
            + persuasiveness * self._weights.get("persuasiveness", 0.25)
        )

        feedback_parts = []
        if ev_quality < 0.5:
            feedback_parts.append("Needs more evidence.")
        if logic < 0.5:
            feedback_parts.append("Improve logical structure.")
        if novelty < 0.5:
            feedback_parts.append("Add novel perspectives.")

        score = ArgumentScore(
            evidence_quality=round(ev_quality, 3),
            logical_consistency=round(logic, 3),
            novelty=round(novelty, 3),
            persuasiveness=round(persuasiveness, 3),
            overall=round(overall, 3),
            feedback=" ".join(feedback_parts),
        )
        self._scores.append((agent_id, score))
        return score

    def agent_scores(self, agent_id: str) -> list[ArgumentScore]:
        """Get all scores for an agent."""
        return [s for aid, s in self._scores if aid == agent_id]

    def leaderboard(self) -> list[tuple[str, float]]:
        """Aggregate scores per agent, sorted descending."""
        totals: dict[str, list[float]] = {}
        for aid, score in self._scores:
            totals.setdefault(aid, []).append(score.overall)
        averages = [
            (aid, round(sum(scores) / len(scores), 3))
            for aid, scores in totals.items()
        ]
        return sorted(averages, key=lambda x: x[1], reverse=True)

    def _assess_logic(self, content: str) -> float:
        """Heuristic logic score based on structure indicators."""
        indicators = ["because", "therefore", "however", "since", "given that", "thus"]
        found = sum(1 for i in indicators if i in content.lower())
        return min(found * 0.2, 1.0)

    def _assess_novelty(self, content: str, prior: list[str]) -> float:
        """Heuristic novelty — how different from prior arguments."""
        if not prior:
            return 0.8
        words = set(content.lower().split())
        overlap_ratios = []
        for p in prior:
            pwords = set(p.lower().split())
            if not words:
                overlap_ratios.append(1.0)
                continue
            overlap = len(words & pwords) / max(len(words), 1)
            overlap_ratios.append(overlap)
        avg_overlap = sum(overlap_ratios) / len(overlap_ratios)
        return round(max(1.0 - avg_overlap, 0.0), 3)

    def _assess_persuasiveness(self, content: str, evidence: list[str]) -> float:
        """Heuristic persuasiveness based on length and evidence."""
        length_score = min(len(content) / 500, 1.0)
        evidence_bonus = min(len(evidence) * 0.15, 0.5)
        return round(min(length_score + evidence_bonus, 1.0), 3)
