"""Graph visualization — DOT and Mermaid output formats."""
from __future__ import annotations

from lidco.codegraph.builder import CodeGraphBuilder


class GraphVisualizer:
    """Renders a code graph in DOT or Mermaid format."""

    def __init__(self, builder: CodeGraphBuilder) -> None:
        self._builder = builder

    def to_dot(self) -> str:
        """Return the full graph in Graphviz DOT format."""
        lines = ["digraph codegraph {"]
        for node in self._builder.nodes():
            label = f'{node.name} ({node.kind})'
            lines.append(f'  "{node.name}" [label="{label}"];')
        for edge in self._builder.edges():
            lines.append(f'  "{edge.source}" -> "{edge.target}" [label="{edge.kind}"];')
        lines.append("}")
        return "\n".join(lines)

    def to_mermaid(self) -> str:
        """Return the full graph in Mermaid flowchart format."""
        lines = ["flowchart TD"]
        for node in self._builder.nodes():
            lines.append(f"  {node.name}[{node.name}]")
        for edge in self._builder.edges():
            lines.append(f"  {edge.source} -->|{edge.kind}| {edge.target}")
        return "\n".join(lines)

    def highlight_path(self, path: list[str]) -> str:
        """Return DOT with highlighted nodes along *path*."""
        highlighted = set(path)
        lines = ["digraph codegraph {"]
        for node in self._builder.nodes():
            label = f'{node.name} ({node.kind})'
            if node.name in highlighted:
                lines.append(
                    f'  "{node.name}" [label="{label}" style=filled fillcolor=yellow];'
                )
            else:
                lines.append(f'  "{node.name}" [label="{label}"];')
        for edge in self._builder.edges():
            lines.append(f'  "{edge.source}" -> "{edge.target}" [label="{edge.kind}"];')
        lines.append("}")
        return "\n".join(lines)

    def filter_by_file(self, file: str) -> str:
        """Return DOT showing only nodes belonging to *file*."""
        names_in_file = {n.name for n in self._builder.nodes() if n.file == file}
        lines = ["digraph codegraph {"]
        for node in self._builder.nodes():
            if node.name in names_in_file:
                label = f'{node.name} ({node.kind})'
                lines.append(f'  "{node.name}" [label="{label}"];')
        for edge in self._builder.edges():
            if edge.source in names_in_file and edge.target in names_in_file:
                lines.append(
                    f'  "{edge.source}" -> "{edge.target}" [label="{edge.kind}"];'
                )
        lines.append("}")
        return "\n".join(lines)
