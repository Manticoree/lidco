"""Memory staleness decay — deprioritize old unused memories."""
from __future__ import annotations

import time
from dataclasses import dataclass


# Import AgentMemory lazily to avoid circular imports
def _get_agent_memory_class():
    from .agent_memory import AgentMemory
    return AgentMemory


def staleness_score(memory) -> float:
    """Compute staleness: age_days / (1 + use_count). Higher = more stale."""
    now = time.time()
    created_at = getattr(memory, "created_at", now)
    use_count = getattr(memory, "use_count", 0)
    age_days = max(0.0, (now - created_at) / 86400)
    return age_days / (1 + use_count)


def freshness_score(memory) -> float:
    """Inverse of staleness (higher = fresher)."""
    s = staleness_score(memory)
    return 1.0 / (1.0 + s)


class StalenessRanker:
    """Rank and expire memories based on staleness."""

    def rank(self, memories: list) -> list:
        """Sort memories by freshness descending (freshest first)."""
        return sorted(memories, key=freshness_score, reverse=True)

    def expire(self, memories: list, ttl_days: float) -> list:
        """Filter out memories older than ttl_days."""
        now = time.time()
        cutoff = now - ttl_days * 86400
        return [m for m in memories if getattr(m, "created_at", now) >= cutoff]

    def split_fresh_stale(self, memories: list, threshold: float = 7.0) -> tuple[list, list]:
        """Split into (fresh, stale) based on staleness_score threshold."""
        fresh = [m for m in memories if staleness_score(m) <= threshold]
        stale = [m for m in memories if staleness_score(m) > threshold]
        return fresh, stale
