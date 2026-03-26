"""DataPipeline — composable ETL pipeline (stdlib only)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable


@runtime_checkable
class PipelineStep(Protocol):
    """Protocol for pipeline steps."""

    name: str

    def process(self, data: list) -> list: ...


@dataclass
class StepResult:
    """Result of a single step recorded during dry_run."""

    step_name: str
    input_count: int
    output_count: int


class FilterStep:
    """Keep items matching *predicate*."""

    def __init__(self, predicate: Callable[[Any], bool], name: str = "filter") -> None:
        self.name = name
        self._predicate = predicate

    def process(self, data: list) -> list:
        return [item for item in data if self._predicate(item)]


class MapStep:
    """Transform each item with *transform*."""

    def __init__(self, transform: Callable[[Any], Any], name: str = "map") -> None:
        self.name = name
        self._transform = transform

    def process(self, data: list) -> list:
        return [self._transform(item) for item in data]


class SortStep:
    """Sort items, optionally by *key*."""

    def __init__(
        self,
        key: Callable[[Any], Any] | None = None,
        reverse: bool = False,
        name: str = "sort",
    ) -> None:
        self.name = name
        self._key = key
        self._reverse = reverse

    def process(self, data: list) -> list:
        return sorted(data, key=self._key, reverse=self._reverse)


class LimitStep:
    """Take first *n* items."""

    def __init__(self, n: int, name: str = "limit") -> None:
        if n < 0:
            raise ValueError(f"n must be non-negative, got {n}")
        self.name = name
        self._n = n

    def process(self, data: list) -> list:
        return data[: self._n]


class UniqueStep:
    """Deduplicate items, preserving order."""

    def __init__(
        self,
        key: Callable[[Any], Any] | None = None,
        name: str = "unique",
    ) -> None:
        self.name = name
        self._key = key

    def process(self, data: list) -> list:
        seen: set = set()
        result: list = []
        for item in data:
            k = self._key(item) if self._key is not None else item
            if k not in seen:
                seen.add(k)
                result.append(item)
        return result


class DataPipeline:
    """
    Composable data pipeline.

    Parameters
    ----------
    name:
        Pipeline name for display/logging.

    Example
    -------
    >>> pipeline = (
    ...     DataPipeline("example")
    ...     .add_step(FilterStep(lambda x: x > 0))
    ...     .add_step(MapStep(lambda x: x * 2))
    ...     .add_step(LimitStep(5))
    ... )
    >>> pipeline.run([-1, 1, 2, 3, 4, 5, 6])
    [2, 4, 6, 8, 10]
    """

    def __init__(self, name: str = "pipeline") -> None:
        self.name = name
        self._steps: list[PipelineStep] = []

    @property
    def steps(self) -> list[PipelineStep]:
        """Return a copy of the steps list."""
        return list(self._steps)

    def add_step(self, step: PipelineStep) -> "DataPipeline":
        """Append *step* and return *self* for fluent chaining."""
        self._steps.append(step)
        return self

    def clear(self) -> None:
        """Remove all steps."""
        self._steps = []

    def run(self, data: list) -> list:
        """
        Execute all steps sequentially and return the final result.

        Raises
        ------
        RuntimeError
            If no steps have been added.
        """
        if not self._steps:
            raise RuntimeError("Pipeline has no steps — add at least one step before calling run()")
        result = list(data)
        for step in self._steps:
            result = step.process(result)
        return result

    def dry_run(self, data: list) -> list[StepResult]:
        """
        Execute all steps and return per-step counts without raising on empty pipeline.

        Returns an empty list if no steps are configured.
        """
        results: list[StepResult] = []
        current = list(data)
        for step in self._steps:
            before = len(current)
            current = step.process(current)
            results.append(StepResult(step.name, before, len(current)))
        return results
