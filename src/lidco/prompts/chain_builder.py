"""Q131: Sequential prompt chain builder."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from lidco.prompts.template_engine import PromptTemplateEngine, RenderContext


@dataclass
class ChainStep:
    name: str
    template: str
    output_key: str
    stop_if_empty: bool = False


@dataclass
class ChainResult:
    steps_run: int
    outputs: dict[str, str]
    final_output: str


class PromptChain:
    """Run a sequence of prompt steps, feeding outputs forward."""

    def __init__(self, engine: PromptTemplateEngine | None = None) -> None:
        self._engine = engine or PromptTemplateEngine()
        self._steps: list[ChainStep] = []

    def add_step(self, step: ChainStep) -> "PromptChain":
        self._steps.append(step)
        return self

    def run(
        self, variables: dict, execute_fn: Callable[[str], str]
    ) -> ChainResult:
        """Execute each step, accumulating outputs into *variables*."""
        context_vars = dict(variables)
        outputs: dict[str, str] = {}
        steps_run = 0
        final_output = ""

        for step in self._steps:
            rendered = self._engine.render(
                step.template, RenderContext(variables=context_vars)
            )
            result = execute_fn(rendered)
            outputs[step.output_key] = result
            context_vars[step.output_key] = result
            steps_run += 1
            final_output = result

            if step.stop_if_empty and not result.strip():
                break

        return ChainResult(
            steps_run=steps_run,
            outputs=outputs,
            final_output=final_output,
        )

    def clear(self) -> None:
        self._steps.clear()
