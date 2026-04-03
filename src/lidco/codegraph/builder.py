"""Code graph builder — nodes and edges representing code symbols and relationships."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GraphNode:
    """A node in the code graph representing a symbol."""

    name: str
    kind: str
    file: str
    line: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class GraphEdge:
    """A directed edge between two symbols."""

    source: str
    target: str
    kind: str  # "calls", "inherits", "imports", "depends"


class CodeGraphBuilder:
    """Builds a graph of code symbols and their relationships."""

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []

    def add_node(self, node: GraphNode) -> None:
        """Add a node to the graph."""
        self._nodes = {**self._nodes, node.name: node}

    def add_edge(self, edge: GraphEdge) -> None:
        """Add an edge to the graph."""
        self._edges = [*self._edges, edge]

    def build_from_symbols(self, symbols: list[dict]) -> None:
        """Build graph from a list of symbol dicts.

        Each dict has keys: name, kind, file, and optionally calls (list of names).
        """
        for sym in symbols:
            node = GraphNode(
                name=sym["name"],
                kind=sym.get("kind", "function"),
                file=sym.get("file", ""),
                line=sym.get("line", 0),
                metadata=sym.get("metadata", {}),
            )
            self.add_node(node)

        for sym in symbols:
            for callee in sym.get("calls", []):
                self.add_edge(GraphEdge(source=sym["name"], target=callee, kind="calls"))

    def get_node(self, name: str) -> GraphNode | None:
        """Return node by name, or None."""
        return self._nodes.get(name)

    def get_edges(self, source: str) -> list[GraphEdge]:
        """Return all edges originating from *source*."""
        return [e for e in self._edges if e.source == source]

    def nodes(self) -> list[GraphNode]:
        """Return all nodes."""
        return list(self._nodes.values())

    def edges(self) -> list[GraphEdge]:
        """Return all edges."""
        return list(self._edges)

    def to_dict(self) -> dict:
        """Serialize graph to a plain dict."""
        return {
            "nodes": [
                {
                    "name": n.name,
                    "kind": n.kind,
                    "file": n.file,
                    "line": n.line,
                    "metadata": n.metadata,
                }
                for n in self._nodes.values()
            ],
            "edges": [
                {"source": e.source, "target": e.target, "kind": e.kind}
                for e in self._edges
            ],
        }
