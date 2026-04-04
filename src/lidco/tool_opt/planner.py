"""ToolPlanner — plan, order, batch and parallelise tool calls."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlannedCall:
    """A single planned tool invocation."""

    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    depends_on: list[int] = field(default_factory=list)
    _index: int = -1


@dataclass
class OptimizedPlan:
    """Result of optimize(): ordered calls with parallel groups."""

    ordered: list[PlannedCall]
    parallel_groups: list[list[PlannedCall]]
    batched_reads: list[list[PlannedCall]]


class ToolPlanner:
    """Build, reorder, batch and parallelise a set of planned tool calls."""

    def __init__(self) -> None:
        self._calls: list[PlannedCall] = []

    def add_call(
        self,
        tool: str,
        args: dict[str, Any] | None = None,
        depends_on: list[int] | None = None,
    ) -> int:
        """Add a call and return its index."""
        idx = len(self._calls)
        call = PlannedCall(
            tool=tool,
            args=args if args is not None else {},
            depends_on=depends_on if depends_on is not None else [],
            _index=idx,
        )
        self._calls.append(call)
        return idx

    @property
    def calls(self) -> list[PlannedCall]:
        return list(self._calls)

    # -- ordering -----------------------------------------------------

    def plan(self) -> list[PlannedCall]:
        """Return calls in topologically-sorted order (by depends_on)."""
        visited: set[int] = set()
        result: list[PlannedCall] = []

        def visit(idx: int) -> None:
            if idx in visited:
                return
            visited.add(idx)
            for dep in self._calls[idx].depends_on:
                visit(dep)
            result.append(self._calls[idx])

        for i in range(len(self._calls)):
            visit(i)
        return result

    # -- batching -----------------------------------------------------

    def batch_reads(self, calls: list[PlannedCall] | None = None) -> list[list[PlannedCall]]:
        """Group consecutive read-like calls into batches."""
        source = calls if calls is not None else self._calls
        batches: list[list[PlannedCall]] = []
        current: list[PlannedCall] = []
        for c in source:
            if c.tool.lower() in ("read", "file_read", "glob", "grep"):
                current.append(c)
            else:
                if current:
                    batches.append(current)
                    current = []
        if current:
            batches.append(current)
        return batches

    # -- parallelism --------------------------------------------------

    def parallelizable(self) -> list[list[PlannedCall]]:
        """Return groups of calls that can run in parallel (no inter-deps)."""
        # Kahn's algorithm by layer
        in_degree: dict[int, int] = {i: 0 for i in range(len(self._calls))}
        for c in self._calls:
            for dep in c.depends_on:
                in_degree[c._index] += 1

        remaining = dict(in_degree)
        layers: list[list[PlannedCall]] = []
        done: set[int] = set()

        while remaining:
            layer = [i for i, d in remaining.items() if d == 0]
            if not layer:
                break  # cycle guard
            layers.append([self._calls[i] for i in sorted(layer)])
            done.update(layer)
            for i in layer:
                del remaining[i]
            for i in list(remaining):
                count = sum(1 for dep in self._calls[i].depends_on if dep not in done)
                remaining[i] = count

        return layers

    # -- full optimise ------------------------------------------------

    def optimize(self) -> OptimizedPlan:
        """Return an OptimizedPlan with ordered calls, parallel groups and batched reads."""
        ordered = self.plan()
        parallel = self.parallelizable()
        batched = self.batch_reads(ordered)
        return OptimizedPlan(
            ordered=ordered,
            parallel_groups=parallel,
            batched_reads=batched,
        )
