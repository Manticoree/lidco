"""DiagramRenderer — mermaid and ASCII diagram rendering (stdlib only)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DiagramNode:
    """A single node in a diagram."""

    id: str
    label: str
    shape: str = "box"


@dataclass
class DiagramEdge:
    """A directed edge between two nodes."""

    from_id: str
    to_id: str
    label: str = ""
    arrow: str = "-->"


@dataclass
class MermaidDiagram:
    """Specification for a Mermaid diagram."""

    diagram_type: str = "graph"
    direction: str = "TD"
    nodes: list[DiagramNode] = field(default_factory=list)
    edges: list[DiagramEdge] = field(default_factory=list)
    raw: str = ""


@dataclass
class AsciiDiagram:
    """Specification for an ASCII box-art diagram."""

    nodes: list[DiagramNode] = field(default_factory=list)
    edges: list[DiagramEdge] = field(default_factory=list)
    title: str = ""


@dataclass
class RenderResult:
    """Output of a render operation."""

    text: str
    format: str  # "mermaid" or "ascii"
    mime_type: str  # "text/x-mermaid" or "text/plain"


class DiagramRenderer:
    """Renders MermaidDiagram and AsciiDiagram into text."""

    def render(self, diagram: MermaidDiagram | AsciiDiagram) -> RenderResult:
        """Dispatch to the correct renderer based on type."""
        if isinstance(diagram, MermaidDiagram):
            return self.render_mermaid(diagram)
        if isinstance(diagram, AsciiDiagram):
            return self.render_ascii(diagram)
        raise TypeError(f"Unsupported diagram type: {type(diagram).__name__}")

    def render_mermaid(self, diagram: MermaidDiagram) -> RenderResult:
        """Render a Mermaid-syntax diagram."""
        if diagram.raw:
            return RenderResult(
                text=diagram.raw,
                format="mermaid",
                mime_type="text/x-mermaid",
            )

        lines: list[str] = [f"{diagram.diagram_type} {diagram.direction}"]

        _shape_map = {
            "box": ("[", "]"),
            "circle": ("(", ")"),
            "diamond": ("{", "}"),
        }

        for node in diagram.nodes:
            left, right = _shape_map.get(node.shape, ("[", "]"))
            lines.append(f"  {node.id}{left}{node.label}{right}")

        for edge in diagram.edges:
            if edge.label:
                lines.append(f"  {edge.from_id} {edge.arrow} {edge.to_id} : {edge.label}")
            else:
                lines.append(f"  {edge.from_id} {edge.arrow} {edge.to_id}")

        text = "\n".join(lines)
        return RenderResult(text=text, format="mermaid", mime_type="text/x-mermaid")

    def render_ascii(self, diagram: AsciiDiagram) -> RenderResult:
        """Render pure-text box-art. No external deps."""
        lines: list[str] = []

        if diagram.title:
            lines.append(diagram.title)
            lines.append("")

        if not diagram.nodes:
            text = "\n".join(lines) if lines else "(empty diagram)"
            return RenderResult(text=text, format="ascii", mime_type="text/plain")

        # Build boxes
        node_map: dict[str, str] = {}
        boxes: list[str] = []
        for node in diagram.nodes:
            label = node.label
            width = len(label) + 4
            top = "+" + "-" * (width - 2) + "+"
            mid = "| " + label + " |"
            bot = "+" + "-" * (width - 2) + "+"
            box = f"{top}\n{mid}\n{bot}"
            boxes.append(box)
            node_map[node.id] = label

        # Lay out boxes inline with arrows
        if diagram.edges:
            # Render connected nodes in edge order
            rendered_parts: list[str] = []
            seen: set[str] = set()
            for edge in diagram.edges:
                if edge.from_id not in seen:
                    seen.add(edge.from_id)
                    label = node_map.get(edge.from_id, edge.from_id)
                    rendered_parts.append(self._make_box(label))
                rendered_parts.append(" --> ")
                if edge.to_id not in seen:
                    seen.add(edge.to_id)
                    label = node_map.get(edge.to_id, edge.to_id)
                    rendered_parts.append(self._make_box(label))
            lines.append("".join(rendered_parts))
        else:
            # Just list boxes
            lines.extend(boxes)

        text = "\n".join(lines)
        return RenderResult(text=text, format="ascii", mime_type="text/plain")

    def _make_box(self, label: str) -> str:
        """Create a single-line box representation."""
        width = len(label) + 4
        top = "+" + "-" * (width - 2) + "+"
        mid = "| " + label + " |"
        bot = "+" + "-" * (width - 2) + "+"
        return f"{top}\n{mid}\n{bot}"

    def as_mcp_tool(self) -> dict:
        """Return MCP tool schema."""
        return {
            "name": "diagram_renderer",
            "description": "Render diagrams in Mermaid or ASCII format",
            "input_schema": {
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": ["mermaid", "ascii"],
                        "description": "Output format",
                    },
                    "nodes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "label": {"type": "string"},
                            },
                            "required": ["id", "label"],
                        },
                    },
                    "edges": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "from_id": {"type": "string"},
                                "to_id": {"type": "string"},
                                "label": {"type": "string"},
                            },
                            "required": ["from_id", "to_id"],
                        },
                    },
                },
                "required": ["format"],
            },
        }
