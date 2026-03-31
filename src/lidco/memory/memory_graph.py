"""Q130 — Agent Memory Graph: MemoryGraph."""
from __future__ import annotations

from typing import Optional

from lidco.memory.memory_node import MemoryEdge, MemoryNode


class MemoryGraph:
    """Directed graph of MemoryNode objects connected by MemoryEdge relations."""

    def __init__(self) -> None:
        self._nodes: dict[str, MemoryNode] = {}
        self._edges: list[MemoryEdge] = []

    def add_node(self, node: MemoryNode) -> None:
        self._nodes[node.id] = node

    def add_edge(self, edge: MemoryEdge) -> None:
        self._edges.append(edge)

    def get_node(self, id: str) -> Optional[MemoryNode]:
        return self._nodes.get(id)

    def neighbors(self, id: str) -> list[MemoryNode]:
        neighbor_ids: set[str] = set()
        for edge in self._edges:
            if edge.source_id == id and edge.target_id in self._nodes:
                neighbor_ids.add(edge.target_id)
            elif edge.target_id == id and edge.source_id in self._nodes:
                neighbor_ids.add(edge.source_id)
        return [self._nodes[nid] for nid in neighbor_ids]

    def edges_from(self, id: str) -> list[MemoryEdge]:
        return [e for e in self._edges if e.source_id == id]

    def edges_to(self, id: str) -> list[MemoryEdge]:
        return [e for e in self._edges if e.target_id == id]

    def remove_node(self, id: str) -> bool:
        if id not in self._nodes:
            return False
        del self._nodes[id]
        self._edges = [
            e for e in self._edges if e.source_id != id and e.target_id != id
        ]
        return True

    def search(self, query: str) -> list[MemoryNode]:
        q = query.lower()
        results: list[MemoryNode] = []
        for node in self._nodes.values():
            if q in node.content.lower() or any(q in t.lower() for t in node.tags):
                results.append(node)
        return results

    def all_nodes(self) -> list[MemoryNode]:
        return list(self._nodes.values())

    def all_edges(self) -> list[MemoryEdge]:
        return list(self._edges)

    def stats(self) -> dict:
        type_counts: dict[str, int] = {}
        for node in self._nodes.values():
            type_counts[node.node_type] = type_counts.get(node.node_type, 0) + 1
        return {
            "nodes": len(self._nodes),
            "edges": len(self._edges),
            "types": type_counts,
        }
