"""FlameGraphGenerator — generate flame graph data from profile results."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from lidco.profiler.runner import ProfileResult


@dataclass
class FlameNode:
    """Single node in a flame graph tree."""

    name: str
    value: float = 0.0
    children: list[FlameNode] = field(default_factory=list)
    self_time: float = 0.0


class FlameGraphGenerator:
    """Generate flame graph data from profile; collapsible; search; filter."""

    def __init__(self) -> None:
        self._generated: int = 0

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def from_profile(self, result: ProfileResult) -> FlameNode:
        """Convert profile entries to a flame tree."""
        root = FlameNode(name=result.name, value=result.total_time)
        for entry in result.entries:
            child = FlameNode(
                name=entry.get("code", f"line:{entry.get('line', '?')}"),
                value=entry.get("time_ms", 0.0),
                self_time=entry.get("time_ms", 0.0),
            )
            root.children.append(child)
        root.self_time = root.value - sum(c.value for c in root.children)
        if root.self_time < 0:
            root.self_time = 0.0
        self._generated += 1
        return root

    def add_node(self, parent: FlameNode, name: str, value: float) -> FlameNode:
        """Add a child node to *parent* and return it."""
        child = FlameNode(name=name, value=value, self_time=value)
        parent.children.append(child)
        return child

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------

    def flatten(self, root: FlameNode, _depth: int = 0) -> list[dict]:
        """Flat list of {name, depth, value, self_time}."""
        result: list[dict] = [{
            "name": root.name,
            "depth": _depth,
            "value": root.value,
            "self_time": root.self_time,
        }]
        for child in root.children:
            result.extend(self.flatten(child, _depth + 1))
        return result

    def search(self, root: FlameNode, query: str) -> list[FlameNode]:
        """Find nodes whose name contains *query*."""
        found: list[FlameNode] = []
        if query.lower() in root.name.lower():
            found.append(root)
        for child in root.children:
            found.extend(self.search(child, query))
        return found

    def filter_threshold(self, root: FlameNode, min_value: float) -> FlameNode:
        """Return a pruned tree keeping only nodes with value >= *min_value*."""
        filtered_children: list[FlameNode] = []
        for child in root.children:
            if child.value >= min_value:
                filtered_children.append(self.filter_threshold(child, min_value))
        return FlameNode(
            name=root.name,
            value=root.value,
            children=filtered_children,
            self_time=root.self_time,
        )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render_text(self, root: FlameNode, depth: int = 0) -> str:
        """ASCII flame graph."""
        indent = "  " * depth
        lines = [f"{indent}{root.name} ({root.value:.2f}ms)"]
        for child in root.children:
            lines.append(self.render_text(child, depth + 1))
        return "\n".join(lines)

    def export_json(self, root: FlameNode) -> str:
        """Export flame tree as JSON."""
        def _to_dict(node: FlameNode) -> dict:
            return {
                "name": node.name,
                "value": node.value,
                "self_time": node.self_time,
                "children": [_to_dict(c) for c in node.children],
            }
        return json.dumps(_to_dict(root), indent=2)

    def summary(self) -> dict:
        """Summary of generator usage."""
        return {"generated": self._generated}
