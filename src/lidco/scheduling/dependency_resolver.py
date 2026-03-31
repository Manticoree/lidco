"""TaskDependencyResolver — DAG-based dependency resolution (stdlib only)."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DependencyNode:
    """A task node in the dependency graph."""

    task_id: str
    depends_on: list[str] = field(default_factory=list)


@dataclass
class ResolutionResult:
    """Result of topological sort resolution."""

    order: list[str]
    has_cycle: bool
    cycle_path: Optional[list[str]] = None


class DependencyResolver:
    """Resolve task execution order via topological sort."""

    def __init__(self) -> None:
        self._nodes: dict[str, DependencyNode] = {}
        self._done: set[str] = set()

    def add_task(self, task_id: str, depends_on: list[str] | None = None) -> None:
        """Register a task with optional dependencies."""
        node = DependencyNode(task_id=task_id, depends_on=list(depends_on or []))
        self._nodes = {**self._nodes, task_id: node}

    # ---------------------------------------------------------------- resolve

    def resolve(self) -> ResolutionResult:
        """Topological sort. Return *ResolutionResult* with cycle detection."""
        in_degree: dict[str, int] = {tid: 0 for tid in self._nodes}
        adjacency: dict[str, list[str]] = {tid: [] for tid in self._nodes}

        for tid, node in self._nodes.items():
            for dep in node.depends_on:
                if dep in self._nodes:
                    adjacency[dep].append(tid)
                    in_degree[tid] = in_degree.get(tid, 0) + 1

        queue: deque[str] = deque(
            tid for tid, deg in in_degree.items() if deg == 0
        )
        order: list[str] = []

        while queue:
            tid = queue.popleft()
            order.append(tid)
            for child in adjacency.get(tid, []):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if len(order) != len(self._nodes):
            cycle = self._find_cycle()
            return ResolutionResult(order=order, has_cycle=True, cycle_path=cycle)

        return ResolutionResult(order=order, has_cycle=False)

    # ---------------------------------------------------------------- incremental

    def get_ready(self) -> list[str]:
        """Return tasks whose dependencies are all satisfied (done)."""
        ready: list[str] = []
        for tid, node in self._nodes.items():
            if tid in self._done:
                continue
            if all(d in self._done or d not in self._nodes for d in node.depends_on):
                ready.append(tid)
        return ready

    def mark_done(self, task_id: str) -> None:
        """Mark *task_id* as completed."""
        self._done.add(task_id)

    def has_cycle(self) -> bool:
        """Quick cycle check."""
        return self.resolve().has_cycle

    # ---------------------------------------------------------------- private

    def _find_cycle(self) -> list[str]:
        """DFS-based cycle finder; returns one cycle path."""
        WHITE, GRAY, BLACK = 0, 1, 2
        colour: dict[str, int] = {tid: WHITE for tid in self._nodes}
        parent: dict[str, str | None] = {tid: None for tid in self._nodes}

        def _dfs(u: str) -> list[str] | None:
            colour[u] = GRAY
            for dep in self._nodes[u].depends_on:
                if dep not in self._nodes:
                    continue
                if colour[dep] == GRAY:
                    # back-edge → cycle
                    path = [dep, u]
                    cur = u
                    while cur != dep:
                        cur = parent[cur]  # type: ignore[assignment]
                        if cur is None:
                            break
                        path.append(cur)
                    path.reverse()
                    return path
                if colour[dep] == WHITE:
                    parent[dep] = u
                    result = _dfs(dep)
                    if result is not None:
                        return result
            colour[u] = BLACK
            return None

        for tid in self._nodes:
            if colour[tid] == WHITE:
                result = _dfs(tid)
                if result is not None:
                    return result
        return []
