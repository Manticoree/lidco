"""Tests for lidco.memory.memory_node."""
from lidco.memory.memory_node import MemoryEdge, MemoryNode


class TestMemoryNode:
    def test_fields(self):
        n = MemoryNode(id="1", content="Python is a language", node_type="fact")
        assert n.id == "1"
        assert n.content == "Python is a language"
        assert n.node_type == "fact"

    def test_defaults(self):
        n = MemoryNode(id="2", content="concept", node_type="concept")
        assert n.tags == []
        assert n.confidence == 1.0
        assert n.created_at == ""
        assert n.updated_at == ""

    def test_tags(self):
        n = MemoryNode(id="3", content="x", node_type="fact", tags=["python", "lang"])
        assert "python" in n.tags

    def test_confidence(self):
        n = MemoryNode(id="4", content="x", node_type="fact", confidence=0.7)
        assert n.confidence == 0.7

    def test_timestamps(self):
        n = MemoryNode(id="5", content="x", node_type="event", created_at="2024-01-01", updated_at="2024-01-02")
        assert n.created_at == "2024-01-01"
        assert n.updated_at == "2024-01-02"

    def test_node_types(self):
        for ntype in ["fact", "concept", "event", "relation"]:
            n = MemoryNode(id=ntype, content="x", node_type=ntype)
            assert n.node_type == ntype

    def test_tags_default_is_separate(self):
        n1 = MemoryNode(id="a", content="x", node_type="fact")
        n2 = MemoryNode(id="b", content="y", node_type="fact")
        n1.tags.append("tag")
        assert "tag" not in n2.tags


class TestMemoryEdge:
    def test_fields(self):
        e = MemoryEdge(source_id="1", target_id="2", relation="causes")
        assert e.source_id == "1"
        assert e.target_id == "2"
        assert e.relation == "causes"

    def test_default_weight(self):
        e = MemoryEdge(source_id="1", target_id="2", relation="related_to")
        assert e.weight == 1.0

    def test_custom_weight(self):
        e = MemoryEdge(source_id="1", target_id="2", relation="implies", weight=0.5)
        assert e.weight == 0.5

    def test_relation_types(self):
        for rel in ["causes", "related_to", "part_of", "implies"]:
            e = MemoryEdge(source_id="a", target_id="b", relation=rel)
            assert e.relation == rel
