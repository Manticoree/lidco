"""Native TDD pipeline — Task 286.

Orchestrates the spec → test (RED) → code (GREEN) → verify loop.

Pipeline stages:
  1. **spec**   — spec-writer agent generates a structured specification
  2. **test**   — tester agent writes failing tests from the spec (RED)
  3. **run_red**— TestRunner confirms tests fail (validates RED)
  4. **code**   — coder agent implements to pass tests (GREEN)
  5. **run_green** — TestRunner confirms tests pass (GREEN)
  6. **verify** — reviewer agent does final quality check
  If GREEN fails, loop back to step 4 up to ``max_cycles``.

Usage::

    pipeline = TDDPipeline(session)
    result = await pipeline.run("add JWT auth to login endpoint")
    print(result.summary())
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lidco.core.session import Session

from lidco.tdd.runner import TestRunResult, TestRunner

logger = logging.getLogger(__name__)


class TDDStage(str, Enum):
    SPEC = "spec"
    TEST = "test"
    RUN_RED = "run_red"
    CODE = "code"
    RUN_GREEN = "run_green"
    VERIFY = "verify"
    DONE = "done"
    FAILED = "failed"


@dataclass
class TDDResult:
    """Overall result of a TDD pipeline run."""

    task: str
    stage_reached: TDDStage = TDDStage.SPEC
    spec: str = ""
    test_code: str = ""
    implementation: str = ""
    review: str = ""
    red_result: TestRunResult | None = None
    green_result: TestRunResult | None = None
    cycles: int = 0
    error: str = ""

    @property
    def success(self) -> bool:
        return self.stage_reached == TDDStage.DONE

    def summary(self) -> str:
        lines: list[str] = [f"**TDD Pipeline: {self.task[:60]}**\n"]
        stage_emoji = {
            TDDStage.SPEC: "📋",
            TDDStage.TEST: "🔴",
            TDDStage.RUN_RED: "🔴",
            TDDStage.CODE: "🟡",
            TDDStage.RUN_GREEN: "🟢",
            TDDStage.VERIFY: "✅",
            TDDStage.DONE: "✅",
            TDDStage.FAILED: "❌",
        }
        lines.append(f"Stage: {stage_emoji.get(self.stage_reached, '')} {self.stage_reached.value}")
        if self.cycles:
            lines.append(f"Cycles: {self.cycles}")
        if self.red_result:
            lines.append(f"RED: {self.red_result.summary}")
        if self.green_result:
            lines.append(f"GREEN: {self.green_result.summary}")
        if self.error:
            lines.append(f"\n⚠️ Error: {self.error}")
        if self.review:
            lines.append(f"\n**Review:**\n{self.review[:400]}")
        return "\n".join(lines)


_SPEC_PROMPT = """\
You are a specification writer. Generate a concise but complete technical specification for the following task.

Structure your response as:
## Goal
One-sentence summary.

## Inputs / Outputs
List inputs and expected outputs.

## Acceptance Criteria
Numbered list of testable criteria.

## Edge Cases
List important edge cases to handle.

## Test File Location
Where tests should be written (e.g., tests/unit/test_foo.py).

## Implementation File Location
Where the implementation should go (e.g., src/mypackage/foo.py).

Task: {task}
"""

_TEST_PROMPT = """\
You are a TDD test writer. Write pytest tests that FAIL (RED) for the following specification.
Write ONLY the test file content — no explanation, no markdown fences.
Tests must import the implementation module but that module doesn't need to exist yet.
Follow the spec exactly — cover all acceptance criteria and edge cases.

Specification:
{spec}
"""

_CODE_PROMPT = """\
You are a coder. Implement the minimal code to make the following failing tests PASS (GREEN).
Write ONLY the implementation file content — no explanation, no markdown fences.
Do NOT modify the tests.

Specification:
{spec}

Failing test output:
{test_output}
"""

_VERIFY_PROMPT = """\
You are a code reviewer. The following TDD cycle just completed successfully (all tests pass).
Provide a brief quality review (3-5 bullet points): correctness, edge cases, code style.

Specification:
{spec}

Implementation:
{implementation}
"""


class TDDPipeline:
    """Orchestrates a TDD cycle using LIDCO agents.

    Args:
        session: Active LIDCO session.
        test_file: Override where tests are written.
        impl_file: Override where implementation is written.
        max_cycles: Maximum RED→GREEN retry cycles before giving up.
        status_callback: Called with (stage_name, message) for progress updates.
    """

    def __init__(
        self,
        session: "Session",
        test_file: str | None = None,
        impl_file: str | None = None,
        max_cycles: int = 3,
        status_callback: Any = None,
    ) -> None:
        self._session = session
        self._test_file = test_file
        self._impl_file = impl_file
        self._max_cycles = max_cycles
        self._status_callback = status_callback
        self._runner = TestRunner(project_dir=getattr(session, "project_dir", Path.cwd()))

    async def run(self, task: str) -> TDDResult:
        """Execute the full TDD pipeline for *task*."""
        result = TDDResult(task=task)
        try:
            # Stage 1: Spec
            self._emit("spec", "Generating specification…")
            spec = await self._generate_spec(task)
            result.spec = spec
            result.stage_reached = TDDStage.SPEC

            # Stage 2: Write tests (RED)
            self._emit("test", "Writing failing tests…")
            test_code, test_path = await self._write_tests(spec)
            result.test_code = test_code
            result.stage_reached = TDDStage.TEST

            # Stage 3: Confirm RED
            self._emit("run_red", "Running tests (expecting RED)…")
            red = self._runner.run(test_path)
            result.red_result = red
            result.stage_reached = TDDStage.RUN_RED

            # Stage 4–5: Code → GREEN loop
            impl_code = ""
            for cycle in range(1, self._max_cycles + 1):
                result.cycles = cycle
                self._emit("code", f"Implementing (cycle {cycle}/{self._max_cycles})…")
                impl_code = await self._write_implementation(
                    spec,
                    test_output=red.summary if red else "",
                )
                result.implementation = impl_code
                result.stage_reached = TDDStage.CODE

                self._emit("run_green", f"Running tests (cycle {cycle})…")
                green = self._runner.run(test_path)
                result.green_result = green
                result.stage_reached = TDDStage.RUN_GREEN

                if green.passed:
                    break
                red = green  # use latest failure for next cycle prompt

            if not (result.green_result and result.green_result.passed):
                result.stage_reached = TDDStage.FAILED
                result.error = "Tests still failing after max cycles."
                return result

            # Stage 6: Verify
            self._emit("verify", "Running quality review…")
            review = await self._verify(spec, impl_code)
            result.review = review
            result.stage_reached = TDDStage.DONE

        except Exception as exc:
            logger.exception("TDD pipeline error")
            result.stage_reached = TDDStage.FAILED
            result.error = str(exc)

        return result

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _emit(self, stage: str, message: str) -> None:
        if self._status_callback:
            try:
                self._status_callback(stage, message)
            except Exception:
                pass
        logger.info("TDD [%s] %s", stage, message)

    async def _llm_call(self, prompt: str, agent_name: str | None = None) -> str:
        """Delegate to the session orchestrator."""
        response = await self._session.orchestrator.handle(
            prompt,
            agent_name=agent_name,
        )
        return response.content if hasattr(response, "content") else str(response)

    async def _generate_spec(self, task: str) -> str:
        prompt = _SPEC_PROMPT.format(task=task)
        return await self._llm_call(prompt, agent_name="architect")

    async def _write_tests(self, spec: str) -> tuple[str, str]:
        """Write failing tests. Returns (code, file_path)."""
        prompt = _TEST_PROMPT.format(spec=spec)
        test_code = await self._llm_call(prompt, agent_name="tester")

        # Strip markdown fences if present
        test_code = _strip_fences(test_code)

        # Determine file path
        if self._test_file:
            test_path = self._test_file
        else:
            # Try to extract from spec
            test_path = _extract_file_path(spec, "Test File") or "tests/unit/test_tdd_generated.py"

        p = Path(test_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(test_code, encoding="utf-8")
        logger.info("TDD: wrote test file %s", test_path)
        return test_code, test_path

    async def _write_implementation(self, spec: str, test_output: str = "") -> str:
        """Write implementation code."""
        prompt = _CODE_PROMPT.format(spec=spec, test_output=test_output)
        impl_code = await self._llm_call(prompt, agent_name="coder")
        impl_code = _strip_fences(impl_code)

        if self._impl_file:
            impl_path = self._impl_file
        else:
            impl_path = _extract_file_path(spec, "Implementation File") or "src/generated_impl.py"

        p = Path(impl_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(impl_code, encoding="utf-8")
        logger.info("TDD: wrote implementation %s", impl_path)
        return impl_code

    async def _verify(self, spec: str, implementation: str) -> str:
        prompt = _VERIFY_PROMPT.format(spec=spec, implementation=implementation[:2000])
        return await self._llm_call(prompt, agent_name="reviewer")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    """Remove leading/trailing markdown code fences."""
    import re
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _extract_file_path(text: str, section: str) -> str | None:
    """Extract a file path from a spec section like '## Test File Location'."""
    import re
    pattern = re.compile(
        rf"##\s+{re.escape(section)}[^\n]*\n([^\n#]+)", re.IGNORECASE
    )
    m = pattern.search(text)
    if m:
        candidate = m.group(1).strip().strip("`").strip()
        # Validate it looks like a file path
        if "/" in candidate or candidate.endswith(".py"):
            return candidate
    return None
