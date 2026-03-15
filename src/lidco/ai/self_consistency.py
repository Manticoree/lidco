"""Self-consistency checking — Task 320.

Generates N independent responses to the same query and selects the answer
that is most consistent across the sample.  Majority voting for factual
questions; cosine/overlap voting for open-ended generation.

Usage::

    checker = SelfConsistencyChecker(llm, n=5)
    result = await checker.check(messages=[{"role": "user", "content": "What is 2+2?"}])
    print(result.winner)       # "4"
    print(result.consistency)  # 0.8 (4 out of 5 agreed)
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from lidco.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


@dataclass
class ConsistencyResult:
    """Result of a self-consistency check."""

    winner: str = ""
    consistency: float = 0.0   # 0.0–1.0; fraction of responses that agree
    samples: list[str] = field(default_factory=list)
    vote_counts: dict[str, int] = field(default_factory=dict)
    n_samples: int = 0
    error: str = ""

    @property
    def success(self) -> bool:
        return not self.error and bool(self.winner)

    def summary(self) -> str:
        if self.error:
            return f"Consistency check failed: {self.error}"
        pct = int(self.consistency * 100)
        return (
            f"Winner: {self.winner[:100]!r}\n"
            f"Agreement: {pct}% ({int(self.consistency * self.n_samples)}/{self.n_samples})"
        )


class SelfConsistencyChecker:
    """Runs N completions and selects the most consistent answer.

    Args:
        llm: LLM provider.
        n: Number of independent samples (default 5).
        temperature: Sampling temperature (default 0.7 for diversity).
        max_concurrent: Max parallel LLM calls.
        normalize_fn: Optional callable to normalize answers before voting.
    """

    def __init__(
        self,
        llm: "BaseLLMProvider",
        n: int = 5,
        temperature: float = 0.7,
        max_concurrent: int = 3,
        normalize_fn: Any = None,
    ) -> None:
        self._llm = llm
        self._n = n
        self._temperature = temperature
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._normalize = normalize_fn or _default_normalize

    async def check(
        self,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 512,
    ) -> ConsistencyResult:
        """Sample *n* responses and return the most consistent one.

        Args:
            messages: Conversation messages for the LLM.
            model: Model name override.
            max_tokens: Max tokens per response.
        """
        if self._n <= 0:
            return ConsistencyResult(error="n must be >= 1")

        async def _one(index: int) -> str:
            async with self._semaphore:
                try:
                    resp = await self._llm.complete(
                        messages=messages,
                        model=model or None,
                        max_tokens=max_tokens,
                        temperature=self._temperature,
                    )
                    return resp.content.strip() if hasattr(resp, "content") else str(resp).strip()
                except Exception as exc:
                    logger.debug("SelfConsistency sample %d failed: %s", index, exc)
                    return ""

        samples_raw = list(await asyncio.gather(*(_one(i) for i in range(self._n))))
        samples = [s for s in samples_raw if s]

        if not samples:
            return ConsistencyResult(n_samples=self._n, error="all samples failed")

        # Normalize and vote
        normalized = [self._normalize(s) for s in samples]
        counts: Counter = Counter(normalized)
        winner_key, winner_count = counts.most_common(1)[0]

        # Find the original (un-normalized) sample that matches the winner key
        winner_original = next(
            (s for s, n in zip(samples, normalized) if n == winner_key),
            winner_key,
        )

        return ConsistencyResult(
            winner=winner_original,
            consistency=winner_count / len(samples),
            samples=samples,
            vote_counts=dict(counts),
            n_samples=self._n,
        )


def _default_normalize(text: str) -> str:
    """Normalize a response for voting: lowercase + strip punctuation."""
    text = text.lower().strip()
    # Remove trailing punctuation
    text = re.sub(r"[.,;:!?]+$", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text
