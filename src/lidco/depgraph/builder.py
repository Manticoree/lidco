"""Dependency graph builder — nodes, edges, and traversal."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DepNode:
    """A single dependency node."""

    name: str
    version: str = ""
    direct: bool = True
    platform: str = "any"


@dataclass(frozen=True)
class DepEdge:
    """A directed edge between two dependency nodes."""

    source: str
    target: str
    version_constraint: str = ""


class DepGraphBuilder:
    """Builds and queries a dependency graph."""

    def __init__(self) -> None:
        self._nodes: dict[str, DepNode] = {}
        self._edges: list[DepEdge] = []

    # -- mutators (return new-ish state, store internally) -----------------

    def add_node(self, node: DepNode) -> None:
        """Add *node* to the graph (last-write wins on name collision)."""
        self._nodes = {**self._nodes, node.name: node}

    def add_edge(self, edge: DepEdge) -> None:
        """Add *edge* to the graph."""
        self._edges = [*self._edges, edge]

    # -- queries -----------------------------------------------------------

    def direct_deps(self) -> list[DepNode]:
        """Return only direct dependencies."""
        return [n for n in self._nodes.values() if n.direct]

    def transitive_deps(self) -> list[DepNode]:
        """Return only transitive (non-direct) dependencies."""
        return [n for n in self._nodes.values() if not n.direct]

    def all_nodes(self) -> list[DepNode]:
        """Return every node in insertion order."""
        return list(self._nodes.values())

    def all_edges(self) -> list[DepEdge]:
        """Return every edge in insertion order."""
        return list(self._edges)

    def to_dict(self) -> dict:
        """Serialise the graph to a plain dict."""
        return {
            "nodes": [
                {
                    "name": n.name,
                    "version": n.version,
                    "direct": n.direct,
                    "platform": n.platform,
                }
                for n in self._nodes.values()
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "version_constraint": e.version_constraint,
                }
                for e in self._edges
            ],
        }
