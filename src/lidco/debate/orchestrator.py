"""DebateOrchestrator — set up debates between agents with configurable rounds."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class DebateRole(Enum):
    PROPOSITION = "proposition"
    OPPOSITION = "opposition"
    JUDGE = "judge"


@dataclass
class Argument:
    """A single argument submitted by a participant."""

    role: DebateRole
    agent_id: str
    content: str
    round_num: int
    timestamp: float = field(default_factory=time.time)
    evidence: list[str] = field(default_factory=list)
    score: float | None = None


@dataclass
class DebateConfig:
    """Configuration for a debate session."""

    topic: str
    rounds: int = 3
    time_limit_seconds: float | None = None
    require_evidence: bool = False
    voting_enabled: bool = True


@dataclass
class DebateResult:
    """Final result of a debate."""

    topic: str
    winner: str | None
    arguments: list[Argument]
    votes: dict[str, int]
    rounds_completed: int
    consensus: str | None = None


class DebateOrchestrator:
    """Orchestrate multi-agent debates with proposition/opposition/judge roles."""

    def __init__(self, config: DebateConfig | None = None) -> None:
        self._config = config or DebateConfig(topic="")
        self._participants: dict[str, DebateRole] = {}
        self._arguments: list[Argument] = []
        self._votes: dict[str, str] = {}  # voter_id -> voted_for agent_id
        self._current_round: int = 0
        self._started: bool = False
        self._finished: bool = False

    @property
    def config(self) -> DebateConfig:
        return self._config

    @property
    def current_round(self) -> int:
        return self._current_round

    @property
    def is_finished(self) -> bool:
        return self._finished

    def add_participant(self, agent_id: str, role: DebateRole) -> None:
        """Register a participant with a debate role."""
        if self._started:
            raise RuntimeError("Cannot add participants after debate started")
        self._participants[agent_id] = role

    def participants(self) -> dict[str, DebateRole]:
        return dict(self._participants)

    def start(self) -> None:
        """Start the debate."""
        if not self._config.topic:
            raise ValueError("Debate topic must be set")
        prop = [a for a, r in self._participants.items() if r == DebateRole.PROPOSITION]
        opp = [a for a, r in self._participants.items() if r == DebateRole.OPPOSITION]
        if not prop or not opp:
            raise ValueError("Need at least one proposition and one opposition")
        self._started = True
        self._current_round = 1

    def submit_argument(
        self,
        agent_id: str,
        content: str,
        evidence: list[str] | None = None,
    ) -> Argument:
        """Submit an argument for the current round."""
        if not self._started:
            raise RuntimeError("Debate not started")
        if self._finished:
            raise RuntimeError("Debate already finished")
        if agent_id not in self._participants:
            raise ValueError(f"Unknown participant: {agent_id}")
        role = self._participants[agent_id]
        if role == DebateRole.JUDGE:
            raise ValueError("Judges cannot submit arguments")
        if self._config.require_evidence and not evidence:
            raise ValueError("Evidence required for this debate")
        arg = Argument(
            role=role,
            agent_id=agent_id,
            content=content,
            round_num=self._current_round,
            evidence=evidence or [],
        )
        self._arguments.append(arg)
        return arg

    def advance_round(self) -> int:
        """Move to the next round. Returns new round number."""
        if not self._started:
            raise RuntimeError("Debate not started")
        if self._current_round >= self._config.rounds:
            self._finished = True
            return self._current_round
        self._current_round += 1
        return self._current_round

    def cast_vote(self, voter_id: str, for_agent_id: str) -> None:
        """Cast a vote for a participant."""
        if not self._config.voting_enabled:
            raise RuntimeError("Voting not enabled")
        if for_agent_id not in self._participants:
            raise ValueError(f"Unknown agent: {for_agent_id}")
        self._votes[voter_id] = for_agent_id

    def tally_votes(self) -> dict[str, int]:
        """Count votes per agent."""
        tally: dict[str, int] = {}
        for agent_id in self._votes.values():
            tally[agent_id] = tally.get(agent_id, 0) + 1
        return tally

    def arguments_for_round(self, round_num: int) -> list[Argument]:
        """Get all arguments for a specific round."""
        return [a for a in self._arguments if a.round_num == round_num]

    def finish(self) -> DebateResult:
        """Finish the debate and produce a result."""
        self._finished = True
        votes = self.tally_votes()
        winner = max(votes, key=votes.get) if votes else None
        return DebateResult(
            topic=self._config.topic,
            winner=winner,
            arguments=list(self._arguments),
            votes=votes,
            rounds_completed=self._current_round,
        )

    def summary(self) -> dict:
        """Summary of the debate state."""
        return {
            "topic": self._config.topic,
            "rounds": self._config.rounds,
            "current_round": self._current_round,
            "participants": len(self._participants),
            "arguments": len(self._arguments),
            "started": self._started,
            "finished": self._finished,
        }
