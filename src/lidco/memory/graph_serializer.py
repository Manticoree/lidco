"""Q130 — Agent Memory Graph: GraphSerializer."""
from __future__ import annotations

import json

from lidco.memory.memory_graph import MemoryGraph
from lidco.memory.memory_node import MemoryEdge, MemoryNode


class GraphSerializer:
    """Serialize and deserialize MemoryGraph objects."""

    def to_dict(self, graph: MemoryGraph) -> dict:
        return {
            "nodes": [vars(n) for n in graph.all_nodes()],
            "edges": [vars(e) for e in graph.all_edges()],
        }

    def from_dict(self, data: dict) -> MemoryGraph:
        graph = MemoryGraph()
        for n in data.get("nodes", []):
            graph.add_node(MemoryNode(**n))
        for e in data.get("edges", []):
            graph.add_edge(MemoryEdge(**e))
        return graph

    def to_json(self, graph: MemoryGraph) -> str:
        return json.dumps(self.to_dict(graph), indent=2)

    def from_json(self, json_str: str) -> MemoryGraph:
        return self.from_dict(json.loads(json_str))

    def merge(self, graph_a: MemoryGraph, graph_b: MemoryGraph) -> MemoryGraph:
        """Merge two graphs; on id conflict keep node with higher confidence."""
        merged = MemoryGraph()
        # Collect all nodes
        node_map: dict[str, MemoryNode] = {}
        for node in graph_a.all_nodes():
            node_map[node.id] = node
        for node in graph_b.all_nodes():
            existing = node_map.get(node.id)
            if existing is None or node.confidence > existing.confidence:
                node_map[node.id] = node
        for node in node_map.values():
            merged.add_node(node)
        # Collect all edges (deduplicate by source+target+relation)
        seen_edges: set[tuple] = set()
        for edge in graph_a.all_edges() + graph_b.all_edges():
            key = (edge.source_id, edge.target_id, edge.relation)
            if key not in seen_edges:
                seen_edges.add(key)
                merged.add_edge(edge)
        return merged
