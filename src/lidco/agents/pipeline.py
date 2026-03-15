"""Agent pipeline builder — Tasks 390 & 393.

Declarative YAML-driven multi-agent pipelines with sequential/parallel
execution, conditional steps, and human-in-the-loop checkpoints.

Example YAML::

    steps:
      - name: analyse
        agent: architect
      - name: code
        agent: coder
        input_from: analyse
      - name: review
        type: checkpoint
      - name: test
        agent: tester
        parallel: true
      - name: security
        agent: security
        parallel: true

Usage::

    pipeline = AgentPipeline()
    pipeline.load(yaml_str)
    result = await pipeline.run("add OAuth", session, confirm_fn=my_confirm)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from lidco.core.session import Session

logger = logging.getLogger(__name__)


@dataclass
class PipelineStep:
    """One step in a pipeline definition."""

    name: str
    agent: str = ""
    condition: str | None = None    # Python expression: {"last_output": str, "step_results": dict}
    parallel: bool = False
    input_from: str | None = None   # name of step whose output to use as task
    type: str = "step"              # "step" | "checkpoint"


@dataclass
class StepResult:
    """Result of one pipeline step execution."""

    name: str
    agent: str
    output: str
    success: bool
    error: str = ""
    skipped: bool = False           # condition evaluated False


@dataclass
class CheckpointResult:
    """Records where the pipeline was paused."""

    step_name: str
    paused: bool = True


@dataclass
class PipelineResult:
    """Aggregated result from a full pipeline run."""

    steps: list[StepResult] = field(default_factory=list)
    success: bool = True
    checkpoint: CheckpointResult | None = None   # set when paused at a checkpoint


class AgentPipeline:
    """Load and execute a declarative YAML agent pipeline."""

    def __init__(self) -> None:
        self._steps: list[PipelineStep] = []

    def load(self, yaml_str: str) -> None:
        """Parse *yaml_str* into pipeline steps.

        Raises ``ValueError`` if the YAML is invalid or missing required fields.
        """
        import yaml  # type: ignore[import]

        try:
            data = yaml.safe_load(yaml_str)
        except Exception as exc:
            raise ValueError(f"Invalid YAML: {exc}") from exc

        if not isinstance(data, dict) or "steps" not in data:
            raise ValueError("Pipeline YAML must have a top-level 'steps' list")

        raw_steps = data["steps"]
        if not isinstance(raw_steps, list):
            raise ValueError("'steps' must be a list")

        steps: list[PipelineStep] = []
        for raw in raw_steps:
            if not isinstance(raw, dict):
                raise ValueError(f"Each step must be a dict, got: {raw!r}")
            name = raw.get("name")
            if not name:
                raise ValueError("Each step must have a 'name' field")
            steps.append(
                PipelineStep(
                    name=str(name),
                    agent=str(raw.get("agent", "")),
                    condition=raw.get("condition"),
                    parallel=bool(raw.get("parallel", False)),
                    input_from=raw.get("input_from"),
                    type=str(raw.get("type", "step")),
                )
            )

        self._steps = steps

    @property
    def steps(self) -> list[PipelineStep]:
        return list(self._steps)

    async def run(
        self,
        task: str,
        session: "Session",
        confirm_fn: Callable[[str, dict[str, StepResult]], Awaitable[bool]] | None = None,
    ) -> PipelineResult:
        """Execute the pipeline for *task*.

        *confirm_fn* is called for checkpoint steps with ``(step_name, step_results_so_far)``
        and should return ``True`` to continue or ``False`` to stop.  When ``None``,
        checkpoints auto-continue.

        Parallel steps (``parallel: True``) are grouped with adjacent parallel steps
        and executed via ``asyncio.gather``.
        """
        if not self._steps:
            return PipelineResult(steps=[], success=True)

        step_results: dict[str, StepResult] = {}
        all_step_results: list[StepResult] = []
        last_output = ""
        pipeline_success = True

        # Group steps into batches: sequential + parallel groups
        batches: list[list[PipelineStep]] = []
        current_batch: list[PipelineStep] = []

        for step in self._steps:
            if step.parallel:
                current_batch.append(step)
            else:
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                batches.append([step])
        if current_batch:
            batches.append(current_batch)

        for batch in batches:
            if len(batch) == 1:
                step = batch[0]
                sr = await self._execute_step(
                    step, task, last_output, step_results, session, confirm_fn
                )
                all_step_results.append(sr)
                step_results[step.name] = sr

                if step.type == "checkpoint" and sr.skipped:
                    # Pipeline paused at checkpoint
                    return PipelineResult(
                        steps=all_step_results,
                        success=False,
                        checkpoint=CheckpointResult(step_name=step.name, paused=True),
                    )

                if not sr.success and not sr.skipped:
                    pipeline_success = False
                    break

                if sr.output:
                    last_output = sr.output
            else:
                # Parallel batch
                parallel_results = await asyncio.gather(
                    *(
                        self._execute_step(s, task, last_output, step_results, session, confirm_fn)
                        for s in batch
                    )
                )
                for step, sr in zip(batch, parallel_results):
                    all_step_results.append(sr)
                    step_results[step.name] = sr
                    if not sr.success and not sr.skipped:
                        pipeline_success = False

                # Use last parallel output as next input
                for sr in reversed(parallel_results):
                    if sr.output:
                        last_output = sr.output
                        break

                if not pipeline_success:
                    break

        return PipelineResult(steps=all_step_results, success=pipeline_success)

    async def _execute_step(
        self,
        step: PipelineStep,
        task: str,
        last_output: str,
        step_results: dict[str, StepResult],
        session: "Session",
        confirm_fn: Callable | None,
    ) -> StepResult:
        """Execute a single step and return its :class:`StepResult`."""
        # Evaluate condition
        if step.condition:
            try:
                ns: dict[str, Any] = {
                    "last_output": last_output,
                    "step_results": {k: v.output for k, v in step_results.items()},
                    "len": len,
                    "str": str,
                    "int": int,
                    "bool": bool,
                }
                if not eval(step.condition, {"__builtins__": {}}, ns):  # noqa: S307
                    return StepResult(
                        name=step.name,
                        agent=step.agent,
                        output="",
                        success=True,
                        skipped=True,
                    )
            except Exception as exc:
                logger.debug("Condition eval failed for step '%s': %s", step.name, exc)

        # Checkpoint handling
        if step.type == "checkpoint":
            if confirm_fn is not None:
                try:
                    should_continue = await confirm_fn(step.name, dict(step_results))
                except Exception:
                    should_continue = True
                if not should_continue:
                    return StepResult(
                        name=step.name,
                        agent="",
                        output="",
                        success=False,
                        skipped=True,   # mark as skipped so caller detects pause
                    )
            return StepResult(
                name=step.name,
                agent="",
                output=last_output,
                success=True,
            )

        # Determine input task
        step_task = task
        if step.input_from and step.input_from in step_results:
            prior = step_results[step.input_from]
            if prior.output:
                step_task = prior.output
        elif last_output and step.input_from == "last":
            step_task = last_output

        agent_name = step.agent or None
        try:
            context = session.get_full_context() if hasattr(session, "get_full_context") else ""
            response = await session.orchestrator.handle(
                step_task,
                agent_name=agent_name,
                context=context,
            )
            content = response.content if hasattr(response, "content") else str(response)
            return StepResult(
                name=step.name,
                agent=step.agent,
                output=content,
                success=True,
            )
        except Exception as exc:
            return StepResult(
                name=step.name,
                agent=step.agent,
                output="",
                success=False,
                error=str(exc),
            )
