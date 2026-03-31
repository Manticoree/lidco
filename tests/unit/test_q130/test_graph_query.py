"""Tests for lidco.memory.graph_query."""
from lidco.memory.memory_graph import MemoryGraph
from lidco.memory.memory_node import MemoryEdge, MemoryNode
from lidco.memory.graph_query import GraphQuery


def make_node(id, content="x", node_type="fact", confidence=1.0, tags=None):
    return MemoryNode(id=id, content=content, node_type=node_type, confidence=confidence, tags=tags or [])


def make_edge(src, tgt, rel="related_to"):
    return MemoryEdge(source_id=src, target_id=tgt, relation=rel)


def build_graph():
    g = MemoryGraph()
    g.add_node(make_node("1", node_type="fact", content="Python"))
    g.add_node(make_node("2", node_type="concept", content="OOP"))
    g.add_node(make_node("3", node_type="event", content="release"))
    g.add_node(make_node("4", node_type="fact", content="Java", tags=["jvm"]))
    g.add_edge(make_edge("1", "2"))
    g.add_edge(make_edge("2", "3"))
    return g


class TestGraphQuery:
    def setup_method(self):
        self.g = build_graph()
        self.q = GraphQuery(self.g)

    def test_find_by_type(self):
        facts = self.q.find_by_type("fact")
        ids = {n.id for n in facts}
        assert ids == {"1", "4"}

    def test_find_by_type_empty(self):
        assert self.q.find_by_type("relation") == []

    def test_find_by_tag(self):
        results = self.q.find_by_tag("jvm")
        assert len(results) == 1
        assert results[0].id == "4"

    def test_find_by_tag_no_match(self):
        assert self.q.find_by_tag("nonexistent") == []

    def test_path_direct(self):
        path = self.q.path("1", "2")
        assert path == ["1", "2"]

    def test_path_indirect(self):
        path = self.q.path("1", "3")
        assert path[0] == "1"
        assert path[-1] == "3"
        assert len(path) >= 3

    def test_path_same_node(self):
        path = self.q.path("1", "1")
        assert path == ["1"]

    def test_path_no_route(self):
        path = self.q.path("1", "4")
        assert path == []

    def test_path_missing_from(self):
        path = self.q.path("ghost", "1")
        assert path == []

    def test_path_missing_to(self):
        path = self.q.path("1", "ghost")
        assert path == []

    def test_subgraph_depth_0(self):
        nodes = self.q.subgraph("1", depth=0)
        assert len(nodes) == 1
        assert nodes[0].id == "1"

    def test_subgraph_depth_1(self):
        nodes = self.q.subgraph("1", depth=1)
        ids = {n.id for n in nodes}
        assert "1" in ids
        assert "2" in ids

    def test_subgraph_depth_2(self):
        nodes = self.q.subgraph("1", depth=2)
        ids = {n.id for n in nodes}
        assert "3" in ids

    def test_subgraph_missing_root(self):
        nodes = self.q.subgraph("ghost")
        assert nodes == []

    def test_high_confidence_all(self):
        results = self.q.high_confidence(0.8)
        assert len(results) == 4

    def test_high_confidence_filtered(self):
        g = MemoryGraph()
        g.add_node(make_node("a", confidence=0.9))
        g.add_node(make_node("b", confidence=0.5))
        q = GraphQuery(g)
        results = q.high_confidence(0.8)
        assert len(results) == 1
        assert results[0].id == "a"

    def test_related_by_relation(self):
        g = MemoryGraph()
        g.add_node(make_node("a"))
        g.add_node(make_node("b"))
        g.add_node(make_node("c"))
        g.add_edge(make_edge("a", "b", "causes"))
        g.add_edge(make_edge("a", "c", "related_to"))
        q = GraphQuery(g)
        results = q.related("a", "causes")
        assert len(results) == 1
        assert results[0].id == "b"

    def test_related_incoming_edge(self):
        g = MemoryGraph()
        g.add_node(make_node("a"))
        g.add_node(make_node("b"))
        g.add_edge(make_edge("b", "a", "causes"))
        q = GraphQuery(g)
        results = q.related("a", "causes")
        assert any(n.id == "b" for n in results)

    def test_related_no_match(self):
        g = MemoryGraph()
        g.add_node(make_node("a"))
        q = GraphQuery(g)
        assert q.related("a", "causes") == []
