"""Best-of-N code generation — Task 290.

Runs N parallel LLM attempts for a task, then selects the best
by running tests against each attempt.

Usage::

    selector = BestOfN(session, n=3)
    result = await selector.run("implement binary search", test_file="tests/test_bs.py")
    print(result.best_code)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lidco.core.session import Session

from lidco.tdd.runner import TestRunResult, TestRunner

logger = logging.getLogger(__name__)


@dataclass
class Attempt:
    """One code generation attempt."""

    index: int
    code: str = ""
    test_result: TestRunResult | None = None
    error: str = ""

    @property
    def score(self) -> int:
        """Higher is better: passed tests count."""
        if self.test_result is None:
            return -1
        return self.test_result.n_passed - self.test_result.n_failed * 2


@dataclass
class BestOfNResult:
    """Result from a best-of-N run."""

    task: str
    n: int
    attempts: list[Attempt] = field(default_factory=list)
    best_index: int = -1
    error: str = ""

    @property
    def best_attempt(self) -> Attempt | None:
        if self.best_index < 0 or not self.attempts:
            return None
        return next((a for a in self.attempts if a.index == self.best_index), None)

    @property
    def best_code(self) -> str:
        a = self.best_attempt
        return a.code if a else ""

    def summary(self) -> str:
        lines = [f"**Best-of-{self.n}: {self.task[:60]}**\n"]
        for a in self.attempts:
            score = a.score
            marker = " ← best" if a.index == self.best_index else ""
            tr = a.test_result
            if tr:
                lines.append(f"  Attempt {a.index}: {tr.n_passed}/{tr.total} passed (score={score}){marker}")
            elif a.error:
                lines.append(f"  Attempt {a.index}: ERROR — {a.error[:60]}{marker}")
            else:
                lines.append(f"  Attempt {a.index}: no tests run{marker}")
        return "\n".join(lines)


class BestOfN:
    """Runs N parallel code generation attempts and picks the best.

    Args:
        session: Active LIDCO session.
        n: Number of attempts to generate.
        agent_name: Agent for code generation (default: "coder").
    """

    def __init__(
        self,
        session: "Session",
        n: int = 3,
        agent_name: str = "coder",
    ) -> None:
        self._session = session
        self._n = max(1, n)
        self._agent_name = agent_name
        self._runner = TestRunner(project_dir=getattr(session, "project_dir", None))

    async def run(
        self,
        task: str,
        test_file: str | None = None,
        impl_file: str | None = None,
        context: str = "",
    ) -> BestOfNResult:
        """Generate N attempts and return the best-scoring one."""
        result = BestOfNResult(task=task, n=self._n)

        async def _one_attempt(index: int) -> Attempt:
            attempt = Attempt(index=index)
            try:
                prompt = f"{task}\n\nAttempt {index} of {self._n} — focus on correctness."
                if context:
                    prompt = f"{context}\n\n{prompt}"
                response = await self._session.orchestrator.handle(
                    prompt,
                    agent_name=self._agent_name,
                )
                code = response.content if hasattr(response, "content") else str(response)
                # Strip fences
                import re
                code = re.sub(r"^```[a-zA-Z]*\n?", "", code.strip())
                code = re.sub(r"\n?```$", "", code)
                attempt.code = code.strip()

                if impl_file and attempt.code:
                    from pathlib import Path
                    p = Path(impl_file)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(attempt.code, encoding="utf-8")

                if test_file:
                    attempt.test_result = self._runner.run(test_file)
            except Exception as exc:
                attempt.error = str(exc)
            return attempt

        attempts = await asyncio.gather(*[_one_attempt(i) for i in range(1, self._n + 1)])
        result.attempts = list(attempts)

        # Select best by score
        if result.attempts:
            best = max(result.attempts, key=lambda a: a.score)
            result.best_index = best.index

        return result
