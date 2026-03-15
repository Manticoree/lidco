"""Agent comparison mode — Task 389.

Runs the same task on multiple agents and presents results side-by-side
so the user can choose the best response.

Usage::

    comparator = AgentComparator()
    result = await comparator.run("refactor auth.py", ["coder", "architect"], session)
    print(result.results[result.best_idx].response)
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


@dataclass
class AgentResult:
    """Result from one agent in a comparison run."""

    agent_name: str
    response: str
    elapsed: float          # seconds
    tokens: int = 0
    success: bool = True
    error: str = ""


@dataclass
class ComparisonResult:
    """Aggregated results from a comparison run."""

    results: list[AgentResult] = field(default_factory=list)
    best_idx: int = 0       # index into results, 0-based


class AgentComparator:
    """Run the same task on multiple agents concurrently and collect results."""

    async def run(
        self,
        task: str,
        agent_names: list[str],
        session: "Session",
    ) -> ComparisonResult:
        """Execute *task* on each agent in *agent_names* concurrently.

        Returns a :class:`ComparisonResult` with one :class:`AgentResult` per agent.
        The ``best_idx`` field defaults to 0 (first agent); callers may override it
        based on user selection.
        """
        if not agent_names:
            return ComparisonResult(results=[], best_idx=0)

        async def _run_one(name: str) -> AgentResult:
            start = time.monotonic()
            try:
                context = session.get_full_context() if hasattr(session, "get_full_context") else ""
                response = await session.orchestrator.handle(
                    task,
                    agent_name=name,
                    context=context,
                )
                elapsed = time.monotonic() - start
                content = response.content if hasattr(response, "content") else str(response)
                tokens = 0
                if hasattr(response, "token_usage") and response.token_usage:
                    tokens = getattr(response.token_usage, "total_tokens", 0)
                return AgentResult(
                    agent_name=name,
                    response=content,
                    elapsed=elapsed,
                    tokens=tokens,
                    success=True,
                )
            except Exception as exc:
                elapsed = time.monotonic() - start
                logger.debug("Agent '%s' failed during comparison: %s", name, exc)
                return AgentResult(
                    agent_name=name,
                    response="",
                    elapsed=elapsed,
                    tokens=0,
                    success=False,
                    error=str(exc),
                )

        results = await asyncio.gather(*(_run_one(name) for name in agent_names))
        return ComparisonResult(results=list(results), best_idx=0)
