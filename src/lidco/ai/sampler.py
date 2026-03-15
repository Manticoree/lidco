"""Multi-model sampling (best-of-N) — Task 314.

Runs N parallel LLM calls (optionally across different models) and selects
the best response using a critic function.

Usage::

    sampler = MultiModelSampler(llm)
    result = await sampler.sample(
        messages=[{"role": "user", "content": "Write a sort function"}],
        n=3,
        critic=lambda responses: max(responses, key=lambda r: len(r.content)),
    )
    print(result.best.content)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from lidco.llm.base import BaseLLMProvider, LLMResponse

logger = logging.getLogger(__name__)


@dataclass
class SamplerAttempt:
    """One attempt in a multi-model sampling run."""

    index: int
    model: str = ""
    response: Any = None  # LLMResponse
    error: str = ""
    score: float = 0.0

    @property
    def success(self) -> bool:
        return not self.error and self.response is not None

    @property
    def content(self) -> str:
        if self.response and hasattr(self.response, "content"):
            return self.response.content
        return ""


@dataclass
class SamplerResult:
    """Result of a multi-model sampling run."""

    attempts: list[SamplerAttempt] = field(default_factory=list)
    best: SamplerAttempt | None = None
    error: str = ""

    @property
    def success(self) -> bool:
        return self.best is not None and self.best.success

    @property
    def n_successful(self) -> int:
        return sum(1 for a in self.attempts if a.success)

    def summary(self) -> str:
        lines = [f"Sampling: {len(self.attempts)} attempts, {self.n_successful} succeeded"]
        if self.best:
            lines.append(f"Best attempt: #{self.best.index} (score={self.best.score:.2f})")
        return "\n".join(lines)


# Default critic: prefer longer, non-empty responses
def _default_critic(attempts: list[SamplerAttempt]) -> SamplerAttempt:
    successful = [a for a in attempts if a.success]
    if not successful:
        return attempts[0] if attempts else SamplerAttempt(index=0, error="no attempts")
    return max(successful, key=lambda a: len(a.content))


class MultiModelSampler:
    """Runs N parallel LLM calls and selects the best response.

    Args:
        llm: Primary LLM provider for completions.
        models: Optional list of model names to sample across.
            If longer than *n*, only the first *n* are used.
            If shorter, models are cycled.
        max_concurrent: Maximum parallel LLM calls.
    """

    def __init__(
        self,
        llm: "BaseLLMProvider",
        models: list[str] | None = None,
        max_concurrent: int = 3,
    ) -> None:
        self._llm = llm
        self._models = models or []
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def sample(
        self,
        messages: list[dict],
        n: int = 3,
        critic: Callable[[list[SamplerAttempt]], SamplerAttempt] | None = None,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **llm_kwargs: Any,
    ) -> SamplerResult:
        """Run N parallel completions and return the best.

        Args:
            messages: Conversation messages for the LLM.
            n: Number of parallel samples.
            critic: Function that selects the best attempt.
                    Defaults to picking the longest successful response.
            model: Model name override (applies to all calls unless ``models`` list set).
            max_tokens: Max tokens per attempt.
            temperature: Sampling temperature.
        """
        if n <= 0:
            return SamplerResult(error="n must be >= 1")

        _critic = critic or _default_critic

        async def _one_attempt(index: int) -> SamplerAttempt:
            chosen_model = self._pick_model(index, model)
            async with self._semaphore:
                try:
                    resp = await self._llm.complete(
                        messages=messages,
                        model=chosen_model or None,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        **llm_kwargs,
                    )
                    return SamplerAttempt(index=index, model=chosen_model or "", response=resp)
                except Exception as exc:
                    logger.debug("Sampler attempt %d failed: %s", index, exc)
                    return SamplerAttempt(index=index, model=chosen_model or "", error=str(exc))

        tasks = [_one_attempt(i) for i in range(n)]
        attempts = list(await asyncio.gather(*tasks))

        best = _critic(attempts)
        for attempt in attempts:
            attempt.score = 1.0 if attempt is best else 0.0

        return SamplerResult(attempts=attempts, best=best)

    def _pick_model(self, index: int, override: str | None) -> str:
        if override:
            return override
        if self._models:
            return self._models[index % len(self._models)]
        return ""
