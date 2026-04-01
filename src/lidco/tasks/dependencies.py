"""DAG-based task dependency resolution."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass


class CyclicDependencyError(Exception):
    """Raised when a dependency cycle is detected."""


@dataclass(frozen=True)
class TaskNode:
    id: str
    depends_on: tuple[str, ...] = ()


class DependencyResolver:
    """Resolve task execution order from a DAG of dependencies."""

    def __init__(self) -> None:
        self._nodes: dict[str, TaskNode] = {}

    def add_node(self, node: TaskNode) -> None:
        self._nodes[node.id] = node

    def has_cycle(self) -> bool:
        """Return True if the dependency graph contains a cycle."""
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def _dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            node = self._nodes.get(node_id)
            if node:
                for dep in node.depends_on:
                    if dep not in visited:
                        if _dfs(dep):
                            return True
                    elif dep in rec_stack:
                        return True
            rec_stack.discard(node_id)
            return False

        for nid in self._nodes:
            if nid not in visited:
                if _dfs(nid):
                    return True
        return False

    def topological_sort(self) -> list[str]:
        """Return nodes in topological order. Raises CyclicDependencyError on cycle."""
        if self.has_cycle():
            raise CyclicDependencyError("Dependency graph contains a cycle")

        in_degree: dict[str, int] = {nid: 0 for nid in self._nodes}
        for node in self._nodes.values():
            for dep in node.depends_on:
                if dep in self._nodes:
                    in_degree[node.id] = in_degree.get(node.id, 0)

        # Recount properly
        in_degree = {nid: 0 for nid in self._nodes}
        for node in self._nodes.values():
            for dep in node.depends_on:
                if dep in self._nodes:
                    in_degree[node.id] += 1

        queue: deque[str] = deque()
        for nid, deg in in_degree.items():
            if deg == 0:
                queue.append(nid)

        result: list[str] = []
        while queue:
            current = queue.popleft()
            result.append(current)
            for node in self._nodes.values():
                if current in node.depends_on and node.id in in_degree:
                    in_degree[node.id] -= 1
                    if in_degree[node.id] == 0:
                        queue.append(node.id)

        return result

    def resolve(self) -> list[list[str]]:
        """Return execution layers (parallel groups) in dependency order."""
        if self.has_cycle():
            raise CyclicDependencyError("Dependency graph contains a cycle")

        if not self._nodes:
            return []

        in_degree: dict[str, int] = {nid: 0 for nid in self._nodes}
        for node in self._nodes.values():
            for dep in node.depends_on:
                if dep in self._nodes:
                    in_degree[node.id] += 1

        layers: list[list[str]] = []
        remaining = dict(in_degree)

        while remaining:
            layer = [nid for nid, deg in remaining.items() if deg == 0]
            if not layer:
                raise CyclicDependencyError("Dependency graph contains a cycle")
            layer.sort()
            layers.append(layer)
            for nid in layer:
                del remaining[nid]
            for nid in remaining:
                node = self._nodes[nid]
                for dep in node.depends_on:
                    if dep in [l for l in layer]:
                        remaining[nid] -= 1

        return layers

    def get_ready(self, completed: set[str]) -> list[str]:
        """Return tasks whose dependencies are all in *completed*."""
        ready: list[str] = []
        for node in self._nodes.values():
            if node.id in completed:
                continue
            deps_met = all(d in completed for d in node.depends_on if d in self._nodes)
            if deps_met:
                ready.append(node.id)
        ready.sort()
        return ready
