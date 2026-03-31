"""Q130 — Agent Memory Graph: GraphQuery."""
from __future__ import annotations

from collections import deque

from lidco.memory.memory_graph import MemoryGraph
from lidco.memory.memory_node import MemoryNode


class GraphQuery:
    """Query helpers for MemoryGraph."""

    def __init__(self, graph: MemoryGraph) -> None:
        self._graph = graph

    def find_by_type(self, node_type: str) -> list[MemoryNode]:
        return [n for n in self._graph.all_nodes() if n.node_type == node_type]

    def find_by_tag(self, tag: str) -> list[MemoryNode]:
        return [n for n in self._graph.all_nodes() if tag in n.tags]

    def path(self, from_id: str, to_id: str) -> list[str]:
        """BFS shortest path; returns list of node ids or [] if unreachable."""
        if from_id not in {n.id for n in self._graph.all_nodes()}:
            return []
        if to_id not in {n.id for n in self._graph.all_nodes()}:
            return []
        if from_id == to_id:
            return [from_id]
        visited: set[str] = {from_id}
        queue: deque[list[str]] = deque([[from_id]])
        while queue:
            current_path = queue.popleft()
            current = current_path[-1]
            for neighbor in self._graph.neighbors(current):
                if neighbor.id in visited:
                    continue
                new_path = current_path + [neighbor.id]
                if neighbor.id == to_id:
                    return new_path
                visited.add(neighbor.id)
                queue.append(new_path)
        return []

    def subgraph(self, root_id: str, depth: int = 2) -> list[MemoryNode]:
        """BFS from root up to *depth* hops."""
        root = self._graph.get_node(root_id)
        if root is None:
            return []
        visited: set[str] = {root_id}
        frontier: list[str] = [root_id]
        result: list[MemoryNode] = [root]
        for _ in range(depth):
            next_frontier: list[str] = []
            for nid in frontier:
                for neighbor in self._graph.neighbors(nid):
                    if neighbor.id not in visited:
                        visited.add(neighbor.id)
                        result.append(neighbor)
                        next_frontier.append(neighbor.id)
            frontier = next_frontier
        return result

    def high_confidence(self, threshold: float = 0.8) -> list[MemoryNode]:
        return [n for n in self._graph.all_nodes() if n.confidence >= threshold]

    def related(self, id: str, relation: str) -> list[MemoryNode]:
        """Neighbors connected by a specific relation type."""
        target_ids: set[str] = set()
        for edge in self._graph.edges_from(id):
            if edge.relation == relation:
                target_ids.add(edge.target_id)
        for edge in self._graph.edges_to(id):
            if edge.relation == relation:
                target_ids.add(edge.source_id)
        return [
            self._graph.get_node(nid)
            for nid in target_ids
            if self._graph.get_node(nid) is not None
        ]
