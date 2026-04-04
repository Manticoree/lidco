"""ToolComposition — compose tools into reusable pipelines."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class PipelineStep:
    """One step in a tool pipeline."""

    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    transform: Callable[[Any], Any] | None = None
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.tool


@dataclass
class Pipeline:
    """An ordered sequence of steps."""

    steps: list[PipelineStep] = field(default_factory=list)
    name: str = "pipeline"


class ToolComposition:
    """Build and execute tool pipelines."""

    def __init__(self) -> None:
        self._steps: list[PipelineStep] = []
        self._tool_fns: dict[str, Callable[..., Any]] = {}

    # -- registration -------------------------------------------------

    def register_tool(self, name: str, fn: Callable[..., Any]) -> None:
        """Register a callable as an available tool for pipelines."""
        self._tool_fns[name] = fn

    # -- building -----------------------------------------------------

    def add_step(
        self,
        tool: str,
        args: dict[str, Any] | None = None,
        transform: Callable[[Any], Any] | None = None,
        name: str = "",
    ) -> PipelineStep:
        """Add a step and return it."""
        step = PipelineStep(
            tool=tool,
            args=args if args is not None else {},
            transform=transform,
            name=name or tool,
        )
        self._steps.append(step)
        return step

    def chain(self, steps: list[PipelineStep] | None = None) -> Pipeline:
        """Create a Pipeline from provided steps or the accumulated steps."""
        chosen = steps if steps is not None else list(self._steps)
        return Pipeline(steps=chosen)

    def clear(self) -> None:
        """Clear accumulated steps."""
        self._steps.clear()

    # -- execution ----------------------------------------------------

    def execute(self, pipeline: Pipeline, context: dict[str, Any] | None = None) -> Any:
        """Execute *pipeline* sequentially, threading results via context.

        Each step receives ``context`` as keyword args merged with its own
        ``args``.  The return value of each step is stored under
        ``context["_last_result"]`` and also passed through the step's
        optional ``transform`` callable before storing.
        """
        ctx: dict[str, Any] = dict(context) if context else {}
        last: Any = None

        for step in pipeline.steps:
            fn = self._tool_fns.get(step.tool)
            if fn is None:
                raise ValueError(f"Tool '{step.tool}' not registered.")

            merged = {**ctx, **step.args}
            result = fn(**merged)

            if step.transform is not None:
                result = step.transform(result)

            last = result
            ctx["_last_result"] = result

        return last
