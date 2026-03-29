"""Tests for DiagramRenderer (Task 709)."""
from __future__ import annotations

import unittest

from lidco.multimodal.diagram_renderer import (
    DiagramNode,
    DiagramEdge,
    MermaidDiagram,
    AsciiDiagram,
    RenderResult,
    DiagramRenderer,
)


class TestDiagramNode(unittest.TestCase):
    def test_create_node(self):
        n = DiagramNode(id="A", label="Node A")
        assert n.id == "A"
        assert n.label == "Node A"
        assert n.shape == "box"

    def test_node_circle_shape(self):
        n = DiagramNode(id="B", label="B", shape="circle")
        assert n.shape == "circle"

    def test_node_diamond_shape(self):
        n = DiagramNode(id="C", label="C", shape="diamond")
        assert n.shape == "diamond"


class TestDiagramEdge(unittest.TestCase):
    def test_create_edge(self):
        e = DiagramEdge(from_id="A", to_id="B")
        assert e.from_id == "A"
        assert e.to_id == "B"
        assert e.arrow == "-->"

    def test_edge_with_label(self):
        e = DiagramEdge(from_id="A", to_id="B", label="yes")
        assert e.label == "yes"

    def test_edge_dashed_arrow(self):
        e = DiagramEdge(from_id="A", to_id="B", arrow="-.->")
        assert e.arrow == "-.->"


class TestMermaidDiagram(unittest.TestCase):
    def test_default_type(self):
        d = MermaidDiagram()
        assert d.diagram_type == "graph"
        assert d.direction == "TD"

    def test_raw_mode(self):
        d = MermaidDiagram(raw="graph LR\n  A-->B")
        assert d.raw == "graph LR\n  A-->B"

    def test_nodes_and_edges(self):
        d = MermaidDiagram(
            nodes=[DiagramNode(id="A", label="A")],
            edges=[DiagramEdge(from_id="A", to_id="B")],
        )
        assert len(d.nodes) == 1
        assert len(d.edges) == 1


class TestRenderResult(unittest.TestCase):
    def test_create_result(self):
        r = RenderResult(text="hello", format="ascii", mime_type="text/plain")
        assert r.text == "hello"
        assert r.format == "ascii"


class TestDiagramRendererMermaid(unittest.TestCase):
    def setUp(self):
        self.renderer = DiagramRenderer()

    def test_render_raw_mermaid(self):
        d = MermaidDiagram(raw="graph LR\n  A-->B")
        result = self.renderer.render(d)
        assert result.format == "mermaid"
        assert "A-->B" in result.text

    def test_render_mermaid_from_nodes(self):
        d = MermaidDiagram(
            nodes=[
                DiagramNode(id="A", label="Node A"),
                DiagramNode(id="B", label="Node B"),
            ],
            edges=[DiagramEdge(from_id="A", to_id="B")],
        )
        result = self.renderer.render_mermaid(d)
        assert result.format == "mermaid"
        assert "graph TD" in result.text
        assert "Node A" in result.text
        assert "Node B" in result.text

    def test_mermaid_mime_type(self):
        d = MermaidDiagram(raw="graph TD\n  X-->Y")
        result = self.renderer.render_mermaid(d)
        assert result.mime_type == "text/x-mermaid"

    def test_mermaid_direction_lr(self):
        d = MermaidDiagram(
            direction="LR",
            nodes=[DiagramNode(id="A", label="A")],
        )
        result = self.renderer.render_mermaid(d)
        assert "graph LR" in result.text

    def test_mermaid_box_shape(self):
        d = MermaidDiagram(
            nodes=[DiagramNode(id="A", label="Test", shape="box")],
        )
        result = self.renderer.render_mermaid(d)
        assert "A[Test]" in result.text or "A[" in result.text

    def test_mermaid_circle_shape(self):
        d = MermaidDiagram(
            nodes=[DiagramNode(id="A", label="Test", shape="circle")],
        )
        result = self.renderer.render_mermaid(d)
        assert "A(" in result.text

    def test_mermaid_diamond_shape(self):
        d = MermaidDiagram(
            nodes=[DiagramNode(id="A", label="Test", shape="diamond")],
        )
        result = self.renderer.render_mermaid(d)
        assert "A{" in result.text

    def test_mermaid_edge_with_label(self):
        d = MermaidDiagram(
            nodes=[
                DiagramNode(id="A", label="A"),
                DiagramNode(id="B", label="B"),
            ],
            edges=[DiagramEdge(from_id="A", to_id="B", label="yes")],
        )
        result = self.renderer.render_mermaid(d)
        assert "yes" in result.text

    def test_mermaid_empty_diagram(self):
        d = MermaidDiagram()
        result = self.renderer.render_mermaid(d)
        assert "graph TD" in result.text

    def test_render_dispatches_mermaid(self):
        d = MermaidDiagram(raw="graph TD\n  A-->B")
        result = self.renderer.render(d)
        assert result.format == "mermaid"


class TestDiagramRendererAscii(unittest.TestCase):
    def setUp(self):
        self.renderer = DiagramRenderer()

    def test_render_ascii_simple(self):
        d = AsciiDiagram(
            nodes=[
                DiagramNode(id="A", label="Node A"),
                DiagramNode(id="B", label="Node B"),
            ],
            edges=[DiagramEdge(from_id="A", to_id="B")],
        )
        result = self.renderer.render_ascii(d)
        assert result.format == "ascii"
        assert "Node A" in result.text
        assert "Node B" in result.text

    def test_ascii_mime_type(self):
        d = AsciiDiagram(nodes=[DiagramNode(id="A", label="X")])
        result = self.renderer.render_ascii(d)
        assert result.mime_type == "text/plain"

    def test_ascii_with_title(self):
        d = AsciiDiagram(
            title="My Diagram",
            nodes=[DiagramNode(id="A", label="A")],
        )
        result = self.renderer.render_ascii(d)
        assert "My Diagram" in result.text

    def test_ascii_box_format(self):
        d = AsciiDiagram(
            nodes=[DiagramNode(id="A", label="Test")],
        )
        result = self.renderer.render_ascii(d)
        assert "+" in result.text
        assert "-" in result.text

    def test_ascii_edge_arrow(self):
        d = AsciiDiagram(
            nodes=[
                DiagramNode(id="A", label="A"),
                DiagramNode(id="B", label="B"),
            ],
            edges=[DiagramEdge(from_id="A", to_id="B")],
        )
        result = self.renderer.render_ascii(d)
        assert "-->" in result.text

    def test_ascii_empty_diagram(self):
        d = AsciiDiagram()
        result = self.renderer.render_ascii(d)
        assert result.format == "ascii"

    def test_render_dispatches_ascii(self):
        d = AsciiDiagram(nodes=[DiagramNode(id="A", label="A")])
        result = self.renderer.render(d)
        assert result.format == "ascii"

    def test_ascii_multiple_nodes(self):
        d = AsciiDiagram(
            nodes=[
                DiagramNode(id="A", label="Alpha"),
                DiagramNode(id="B", label="Beta"),
                DiagramNode(id="C", label="Gamma"),
            ],
            edges=[
                DiagramEdge(from_id="A", to_id="B"),
                DiagramEdge(from_id="B", to_id="C"),
            ],
        )
        result = self.renderer.render_ascii(d)
        assert "Alpha" in result.text
        assert "Beta" in result.text
        assert "Gamma" in result.text


class TestMcpTool(unittest.TestCase):
    def test_as_mcp_tool(self):
        renderer = DiagramRenderer()
        schema = renderer.as_mcp_tool()
        assert "name" in schema
        assert "description" in schema
        assert "input_schema" in schema


if __name__ == "__main__":
    unittest.main()
