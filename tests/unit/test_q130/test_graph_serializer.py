"""Tests for lidco.memory.graph_serializer."""
import json
from lidco.memory.memory_graph import MemoryGraph
from lidco.memory.memory_node import MemoryEdge, MemoryNode
from lidco.memory.graph_serializer import GraphSerializer


def make_node(id, content="x", node_type="fact", confidence=1.0):
    return MemoryNode(id=id, content=content, node_type=node_type, confidence=confidence)


def make_edge(src, tgt, rel="related_to"):
    return MemoryEdge(source_id=src, target_id=tgt, relation=rel)


def build_simple_graph():
    g = MemoryGraph()
    g.add_node(make_node("a", "Alpha"))
    g.add_node(make_node("b", "Beta"))
    g.add_edge(make_edge("a", "b", "implies"))
    return g


class TestGraphSerializer:
    def setup_method(self):
        self.ser = GraphSerializer()

    def test_to_dict_keys(self):
        g = build_simple_graph()
        d = self.ser.to_dict(g)
        assert "nodes" in d
        assert "edges" in d

    def test_to_dict_node_count(self):
        g = build_simple_graph()
        d = self.ser.to_dict(g)
        assert len(d["nodes"]) == 2

    def test_to_dict_edge_count(self):
        g = build_simple_graph()
        d = self.ser.to_dict(g)
        assert len(d["edges"]) == 1

    def test_from_dict_restores_nodes(self):
        g = build_simple_graph()
        d = self.ser.to_dict(g)
        g2 = self.ser.from_dict(d)
        assert g2.get_node("a") is not None
        assert g2.get_node("b") is not None

    def test_from_dict_restores_edges(self):
        g = build_simple_graph()
        d = self.ser.to_dict(g)
        g2 = self.ser.from_dict(d)
        assert len(g2.all_edges()) == 1
        assert g2.all_edges()[0].relation == "implies"

    def test_to_json_is_valid_json(self):
        g = build_simple_graph()
        raw = self.ser.to_json(g)
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_from_json_round_trip(self):
        g = build_simple_graph()
        raw = self.ser.to_json(g)
        g2 = self.ser.from_json(raw)
        assert g2.get_node("a") is not None
        assert g2.get_node("b") is not None

    def test_from_json_edge(self):
        g = build_simple_graph()
        raw = self.ser.to_json(g)
        g2 = self.ser.from_json(raw)
        edges = g2.edges_from("a")
        assert len(edges) == 1

    def test_from_dict_empty(self):
        g = self.ser.from_dict({"nodes": [], "edges": []})
        assert len(g.all_nodes()) == 0
        assert len(g.all_edges()) == 0

    def test_merge_all_nodes(self):
        ga = MemoryGraph()
        ga.add_node(make_node("1", "one"))
        gb = MemoryGraph()
        gb.add_node(make_node("2", "two"))
        merged = self.ser.merge(ga, gb)
        assert merged.get_node("1") is not None
        assert merged.get_node("2") is not None

    def test_merge_conflict_keeps_higher_confidence(self):
        ga = MemoryGraph()
        ga.add_node(make_node("1", "low", confidence=0.4))
        gb = MemoryGraph()
        gb.add_node(make_node("1", "high", confidence=0.9))
        merged = self.ser.merge(ga, gb)
        assert merged.get_node("1").content == "high"

    def test_merge_conflict_a_wins(self):
        ga = MemoryGraph()
        ga.add_node(make_node("1", "better", confidence=0.95))
        gb = MemoryGraph()
        gb.add_node(make_node("1", "worse", confidence=0.3))
        merged = self.ser.merge(ga, gb)
        assert merged.get_node("1").content == "better"

    def test_merge_deduplicates_edges(self):
        ga = MemoryGraph()
        ga.add_node(make_node("a"))
        ga.add_node(make_node("b"))
        ga.add_edge(make_edge("a", "b", "causes"))
        gb = MemoryGraph()
        gb.add_node(make_node("a"))
        gb.add_node(make_node("b"))
        gb.add_edge(make_edge("a", "b", "causes"))
        merged = self.ser.merge(ga, gb)
        assert len(merged.all_edges()) == 1

    def test_merge_includes_all_edges(self):
        ga = MemoryGraph()
        ga.add_node(make_node("a"))
        ga.add_node(make_node("b"))
        ga.add_edge(make_edge("a", "b", "causes"))
        gb = MemoryGraph()
        gb.add_node(make_node("b"))
        gb.add_node(make_node("c"))
        gb.add_edge(make_edge("b", "c", "part_of"))
        merged = self.ser.merge(ga, gb)
        assert len(merged.all_edges()) == 2

    def test_to_dict_node_fields(self):
        g = MemoryGraph()
        n = make_node("x", "some content", node_type="event")
        g.add_node(n)
        d = self.ser.to_dict(g)
        node_dict = d["nodes"][0]
        assert node_dict["id"] == "x"
        assert node_dict["content"] == "some content"
        assert node_dict["node_type"] == "event"

    def test_json_pretty_printed(self):
        g = build_simple_graph()
        raw = self.ser.to_json(g)
        assert "\n" in raw  # indent=2

    def test_merge_empty_graphs(self):
        merged = self.ser.merge(MemoryGraph(), MemoryGraph())
        assert len(merged.all_nodes()) == 0
        assert len(merged.all_edges()) == 0
