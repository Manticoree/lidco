"""ConsensusBuilder — synthesize debate into consensus with voting and dissent."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConsensusResult:
    """Result of consensus building."""

    decision: str
    confidence: float  # 0-1
    majority_pct: float  # percentage of agreement
    supporting_points: list[str] = field(default_factory=list)
    dissenting_points: list[str] = field(default_factory=list)
    abstentions: int = 0


class ConsensusBuilder:
    """Build consensus from debate arguments and votes."""

    def __init__(self) -> None:
        self._positions: dict[str, list[str]] = {}  # agent -> arguments
        self._expertise_weights: dict[str, float] = {}  # agent -> weight
        self._votes: dict[str, str] = {}  # agent -> position_label
        self._dissents: list[str] = []

    def add_position(self, agent_id: str, arguments: list[str]) -> None:
        """Add an agent's position (list of argument summaries)."""
        self._positions[agent_id] = list(arguments)

    def set_expertise_weight(self, agent_id: str, weight: float) -> None:
        """Set expertise weight for weighted voting."""
        self._expertise_weights[agent_id] = max(0.0, min(weight, 1.0))

    def cast_vote(self, agent_id: str, position: str) -> None:
        """Agent votes for a position label (e.g., 'approve', 'reject')."""
        self._votes[agent_id] = position

    def add_dissent(self, reason: str) -> None:
        """Record a dissenting opinion."""
        self._dissents.append(reason)

    def majority_vote(self) -> tuple[str, float]:
        """Simple majority vote. Returns (winning_position, percentage)."""
        if not self._votes:
            return ("none", 0.0)
        counts: dict[str, int] = {}
        for pos in self._votes.values():
            counts[pos] = counts.get(pos, 0) + 1
        winner = max(counts, key=counts.get)
        pct = counts[winner] / len(self._votes)
        return (winner, round(pct, 3))

    def weighted_vote(self) -> tuple[str, float]:
        """Weighted vote by expertise. Returns (winning_position, score)."""
        if not self._votes:
            return ("none", 0.0)
        scores: dict[str, float] = {}
        total_weight = 0.0
        for agent_id, position in self._votes.items():
            w = self._expertise_weights.get(agent_id, 1.0)
            scores[position] = scores.get(position, 0.0) + w
            total_weight += w
        winner = max(scores, key=scores.get)
        pct = scores[winner] / total_weight if total_weight > 0 else 0.0
        return (winner, round(pct, 3))

    def build(self, decision_text: str = "") -> ConsensusResult:
        """Build consensus result."""
        position, majority_pct = self.majority_vote()
        decision = decision_text or f"Consensus: {position}"

        supporting = []
        dissenting = []
        for agent_id, args in self._positions.items():
            vote = self._votes.get(agent_id, "")
            if vote == position:
                supporting.extend(args)
            else:
                dissenting.extend(args)

        dissenting.extend(self._dissents)

        total_voters = len(self._votes)
        abstentions = len(self._positions) - total_voters

        confidence = majority_pct * 0.7 + (1.0 - len(dissenting) / max(len(supporting) + len(dissenting), 1)) * 0.3

        return ConsensusResult(
            decision=decision,
            confidence=round(max(0.0, min(confidence, 1.0)), 3),
            majority_pct=round(majority_pct * 100, 1),
            supporting_points=supporting,
            dissenting_points=dissenting,
            abstentions=max(abstentions, 0),
        )

    def summary(self) -> dict:
        """Summary of consensus state."""
        return {
            "positions": len(self._positions),
            "votes": len(self._votes),
            "dissents": len(self._dissents),
            "weighted_agents": len(self._expertise_weights),
        }
