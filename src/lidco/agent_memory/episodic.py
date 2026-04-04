"""Episodic memory — stores task episodes with outcome, strategy, and files.

Each episode captures what happened during a task execution so the agent
can learn from past successes and failures.
"""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class Episode:
    """A single recorded episode."""

    id: str
    description: str
    outcome: str  # "success" or "failure"
    strategy: str
    files: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower()))


class EpisodicMemory:
    """Store and query task episodes."""

    def __init__(self) -> None:
        self._episodes: list[Episode] = []

    def record(self, episode: dict) -> Episode:
        """Record an episode from a dict.

        Required keys: description, outcome, strategy.
        Optional keys: files, metadata.
        """
        if not episode.get("description"):
            raise ValueError("description is required")
        outcome = episode.get("outcome", "success")
        if outcome not in ("success", "failure"):
            raise ValueError("outcome must be 'success' or 'failure'")
        if not episode.get("strategy"):
            raise ValueError("strategy is required")

        ep = Episode(
            id=uuid.uuid4().hex[:12],
            description=episode["description"],
            outcome=outcome,
            strategy=episode["strategy"],
            files=list(episode.get("files", [])),
            timestamp=episode.get("timestamp", time.time()),
            metadata=dict(episode.get("metadata", {})),
        )
        self._episodes.append(ep)
        return ep

    def search(self, query: str) -> list[Episode]:
        """Search episodes by keyword overlap with description+strategy."""
        if not query.strip():
            return []
        tokens = _tokenize(query)
        scored: list[tuple[float, Episode]] = []
        for ep in self._episodes:
            ep_tokens = _tokenize(ep.description) | _tokenize(ep.strategy)
            overlap = len(tokens & ep_tokens)
            if overlap > 0:
                scored.append((overlap, ep))
        scored.sort(key=lambda x: (-x[0], -x[1].timestamp))
        return [ep for _, ep in scored]

    def by_outcome(self, outcome: str) -> list[Episode]:
        """Filter episodes by outcome ('success' or 'failure')."""
        return [ep for ep in self._episodes if ep.outcome == outcome]

    def recent(self, n: int = 5) -> list[Episode]:
        """Return the *n* most recent episodes."""
        return sorted(self._episodes, key=lambda e: e.timestamp, reverse=True)[:n]

    def all(self) -> list[Episode]:
        """Return all episodes."""
        return list(self._episodes)
