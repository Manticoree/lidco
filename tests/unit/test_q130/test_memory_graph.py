"""Tests for lidco.memory.memory_graph."""
from lidco.memory.memory_graph import MemoryGraph
from lidco.memory.memory_node import MemoryEdge, MemoryNode


def make_node(id, content="x", node_type="fact", **kw):
    return MemoryNode(id=id, content=content, node_type=node_type, **kw)


def make_edge(src, tgt, rel="related_to"):
    return MemoryEdge(source_id=src, target_id=tgt, relation=rel)


class TestMemoryGraph:
    def setup_method(self):
        self.g = MemoryGraph()

    def test_add_and_get_node(self):
        n = make_node("1", "hello")
        self.g.add_node(n)
        assert self.g.get_node("1") is n

    def test_get_missing_returns_none(self):
        assert self.g.get_node("ghost") is None

    def test_add_edge(self):
        self.g.add_node(make_node("a"))
        self.g.add_node(make_node("b"))
        e = make_edge("a", "b")
        self.g.add_edge(e)
        assert len(self.g.edges_from("a")) == 1

    def test_neighbors_via_out_edge(self):
        self.g.add_node(make_node("a"))
        self.g.add_node(make_node("b"))
        self.g.add_edge(make_edge("a", "b"))
        nbrs = self.g.neighbors("a")
        assert any(n.id == "b" for n in nbrs)

    def test_neighbors_via_in_edge(self):
        self.g.add_node(make_node("a"))
        self.g.add_node(make_node("b"))
        self.g.add_edge(make_edge("a", "b"))
        nbrs = self.g.neighbors("b")
        assert any(n.id == "a" for n in nbrs)

    def test_edges_from(self):
        self.g.add_node(make_node("a"))
        self.g.add_node(make_node("b"))
        self.g.add_node(make_node("c"))
        self.g.add_edge(make_edge("a", "b"))
        self.g.add_edge(make_edge("a", "c"))
        edges = self.g.edges_from("a")
        assert len(edges) == 2

    def test_edges_to(self):
        self.g.add_node(make_node("a"))
        self.g.add_node(make_node("b"))
        self.g.add_edge(make_edge("a", "b"))
        edges = self.g.edges_to("b")
        assert len(edges) == 1
        assert edges[0].source_id == "a"

    def test_remove_node(self):
        self.g.add_node(make_node("x"))
        result = self.g.remove_node("x")
        assert result is True
        assert self.g.get_node("x") is None

    def test_remove_node_removes_edges(self):
        self.g.add_node(make_node("a"))
        self.g.add_node(make_node("b"))
        self.g.add_edge(make_edge("a", "b"))
        self.g.remove_node("a")
        assert len(self.g.edges_from("a")) == 0
        assert len(self.g.edges_to("b")) == 0

    def test_remove_missing(self):
        assert self.g.remove_node("ghost") is False

    def test_search_content(self):
        self.g.add_node(make_node("1", content="Python is great"))
        self.g.add_node(make_node("2", content="Java is verbose"))
        results = self.g.search("Python")
        assert len(results) == 1
        assert results[0].id == "1"

    def test_search_tag(self):
        n = make_node("1", content="x")
        n.tags = ["python", "lang"]
        self.g.add_node(n)
        results = self.g.search("python")
        assert len(results) == 1

    def test_search_case_insensitive(self):
        self.g.add_node(make_node("1", content="UPPER CASE"))
        results = self.g.search("upper")
        assert len(results) == 1

    def test_search_no_match(self):
        self.g.add_node(make_node("1", content="nothing"))
        results = self.g.search("xyz_nomatch")
        assert results == []

    def test_all_nodes(self):
        self.g.add_node(make_node("a"))
        self.g.add_node(make_node("b"))
        assert len(self.g.all_nodes()) == 2

    def test_all_edges(self):
        self.g.add_node(make_node("a"))
        self.g.add_node(make_node("b"))
        self.g.add_edge(make_edge("a", "b"))
        assert len(self.g.all_edges()) == 1

    def test_stats(self):
        self.g.add_node(make_node("a", node_type="fact"))
        self.g.add_node(make_node("b", node_type="concept"))
        self.g.add_edge(make_edge("a", "b"))
        s = self.g.stats()
        assert s["nodes"] == 2
        assert s["edges"] == 1
        assert s["types"]["fact"] == 1
        assert s["types"]["concept"] == 1

    def test_stats_empty(self):
        s = self.g.stats()
        assert s["nodes"] == 0
        assert s["edges"] == 0

    def test_overwrite_node(self):
        self.g.add_node(make_node("1", content="old"))
        self.g.add_node(make_node("1", content="new"))
        assert self.g.get_node("1").content == "new"
