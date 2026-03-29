"""Q124 — TaskPipeline: sequential pipeline where each step feeds the next."""
from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class PipelineStep:
    name: str
    fn: Callable  # fn(input) -> output, may be sync or async
    skip_on_error: bool = False


@dataclass
class PipelineResult:
    steps_run: int
    steps_skipped: int
    final_output: Any
    errors: dict[str, str]  # step_name -> error message
    success: bool


class TaskPipeline:
    def __init__(self) -> None:
        self._steps: list[PipelineStep] = []

    def add_step(self, step: PipelineStep) -> None:
        self._steps.append(step)

    def run(self, initial_input: Any = None) -> PipelineResult:
        return asyncio.run(self.run_async(initial_input))

    async def run_async(self, initial_input: Any = None) -> PipelineResult:
        current = initial_input
        steps_run = 0
        steps_skipped = 0
        errors: dict[str, str] = {}

        for step in self._steps:
            try:
                if inspect.iscoroutinefunction(step.fn):
                    current = await step.fn(current)
                else:
                    current = step.fn(current)
                steps_run += 1
            except Exception as exc:
                errors[step.name] = str(exc)
                if step.skip_on_error:
                    steps_skipped += 1
                else:
                    # Stop the pipeline on error
                    return PipelineResult(
                        steps_run=steps_run,
                        steps_skipped=steps_skipped,
                        final_output=current,
                        errors=errors,
                        success=False,
                    )

        return PipelineResult(
            steps_run=steps_run,
            steps_skipped=steps_skipped,
            final_output=current,
            errors=errors,
            success=len(errors) == 0 or all(
                self._steps[i].skip_on_error
                for i, s in enumerate(self._steps)
                if s.name in errors
            ),
        )

    def clear(self) -> None:
        self._steps.clear()
