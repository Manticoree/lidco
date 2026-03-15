"""Model cost comparison tool — Task 426.

Runs the same prompt on multiple models and produces a side-by-side
comparison of tokens, cost, latency, and response quality.

Usage::

    comparator = ModelComparator(session)
    results = await comparator.compare("Explain async/await", ["gpt-4o", "claude-3-5"])
    for r in results:
        print(r.model, r.cost_usd, r.duration_ms)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lidco.core.session import Session

logger = logging.getLogger(__name__)

# Default cost per token in USD (input/output).
# Source: approximate public pricing as of early 2025.
_DEFAULT_COST_PER_TOKEN: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.5e-6, "output": 10e-6},
    "gpt-4o-mini": {"input": 0.15e-6, "output": 0.6e-6},
    "gpt-3.5-turbo": {"input": 0.5e-6, "output": 1.5e-6},
    "claude-3-5-sonnet": {"input": 3e-6, "output": 15e-6},
    "claude-3-5-haiku": {"input": 0.8e-6, "output": 4e-6},
    "claude-sonnet-4-6": {"input": 3e-6, "output": 15e-6},
    "claude-3-opus": {"input": 15e-6, "output": 75e-6},
    "glm-4": {"input": 0.5e-6, "output": 0.5e-6},
}


def _lookup_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Return estimated USD cost for a call using *model*."""
    key = model.lower().split("/")[-1]  # strip provider prefix
    # Fuzzy match
    for k, v in _DEFAULT_COST_PER_TOKEN.items():
        if k in key or key in k:
            return tokens_in * v["input"] + tokens_out * v["output"]
    # Default fallback
    return tokens_in * 1e-6 + tokens_out * 2e-6


@dataclass
class ComparisonResult:
    """Result for one model in a comparison run."""

    model: str
    response: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    error: str = ""

    @property
    def success(self) -> bool:
        return not self.error

    @property
    def quality_chars(self) -> int:
        """Length of response as a rough quality proxy."""
        return len(self.response)

    def as_row(self) -> list[str]:
        """Return values suitable for a Rich table row."""
        if self.error:
            return [self.model, "ERROR", "—", "—", "—", self.error[:40]]
        return [
            self.model,
            f"{self.tokens_in}↑ {self.tokens_out}↓",
            f"${self.cost_usd:.6f}",
            f"{self.duration_ms:.0f}ms",
            str(self.quality_chars),
        ]


class ModelComparator:
    """Runs the same prompt on multiple models and returns a comparison.

    Args:
        session: Active LIDCO session. Its LLM provider is used.
        cost_table: Optional custom cost-per-token dict.
    """

    def __init__(
        self,
        session: "Session",
        cost_table: dict[str, dict[str, float]] | None = None,
    ) -> None:
        self._session = session
        self._cost_table = cost_table or _DEFAULT_COST_PER_TOKEN

    def _estimate_cost(self, model: str, tokens_in: int, tokens_out: int) -> float:
        key = model.lower().split("/")[-1]
        for k, v in self._cost_table.items():
            if k in key or key in k:
                return tokens_in * v["input"] + tokens_out * v["output"]
        return _lookup_cost(model, tokens_in, tokens_out)

    async def _run_one(self, prompt: str, model: str, max_tokens: int) -> ComparisonResult:
        t0 = time.monotonic()
        try:
            llm = getattr(self._session, "llm", None)
            if llm is None:
                raise RuntimeError("No LLM provider on session")

            messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
            params: dict[str, Any] = {
                "messages": messages,
                "model": model,
                "max_tokens": max_tokens,
            }

            resp = await llm.complete(**params)
            duration = (time.monotonic() - t0) * 1000

            content = ""
            if resp:
                content = getattr(resp, "content", "") or ""

            tokens_in = 0
            tokens_out = 0
            if resp and hasattr(resp, "usage") and resp.usage:
                tokens_in = getattr(resp.usage, "prompt_tokens", 0) or 0
                tokens_out = getattr(resp.usage, "completion_tokens", 0) or 0

            cost = self._estimate_cost(model, tokens_in, tokens_out)

            return ComparisonResult(
                model=model,
                response=content,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost,
                duration_ms=duration,
            )

        except Exception as exc:
            duration = (time.monotonic() - t0) * 1000
            logger.debug("Comparison run failed for %s: %s", model, exc)
            return ComparisonResult(model=model, response="", duration_ms=duration, error=str(exc))

    async def compare(
        self,
        prompt: str,
        models: list[str],
        max_tokens: int = 512,
    ) -> list[ComparisonResult]:
        """Run *prompt* on each model concurrently and return results.

        Args:
            prompt: The prompt to send to each model.
            models: List of model identifier strings.
            max_tokens: Token budget for each response.

        Returns:
            List of :class:`ComparisonResult` in the same order as *models*.
        """
        if not models:
            return []
        tasks = [self._run_one(prompt, m, max_tokens) for m in models]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        output: list[ComparisonResult] = []
        for model, r in zip(models, results):
            if isinstance(r, Exception):
                output.append(ComparisonResult(model=model, response="", error=str(r)))
            else:
                output.append(r)
        return output

    def format_table(self, results: list[ComparisonResult]) -> str:
        """Return a plain-text table of comparison results."""
        header = ["Model", "Tokens", "Cost (USD)", "Time", "Quality (chars)"]
        rows = [r.as_row() for r in results]

        # Column widths
        col_widths = [len(h) for h in header]
        for row in rows:
            for i, cell in enumerate(row[:len(header)]):
                col_widths[i] = max(col_widths[i], len(cell))

        sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
        fmt = "| " + " | ".join(f"{{:<{w}}}" for w in col_widths) + " |"

        lines = [sep, fmt.format(*header), sep]
        for row in rows:
            # Pad short rows
            padded = list(row) + [""] * (len(header) - len(row))
            lines.append(fmt.format(*padded[:len(header)]))
        lines.append(sep)
        return "\n".join(lines)
