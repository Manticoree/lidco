"""Tests for Q329 — KnowledgeGraph."""
from __future__ import annotations

import unittest

from lidco.knowledge.graph import (
    Entity,
    EntityType,
    KnowledgeGraph,
    QueryResult,
    Relationship,
    RelationType,
)


class TestEntity(unittest.TestCase):
    def test_exact_name_match_score_1(self) -> None:
        e = Entity(id="1", name="AuthService", entity_type=EntityType.CLASS)
        self.assertEqual(e.matches("authservice"), 1.0)

    def test_partial_name_match(self) -> None:
        e = Entity(id="1", name="AuthService", entity_type=EntityType.CLASS)
        score = e.matches("auth")
        self.assertGreater(score, 0.0)

    def test_description_match(self) -> None:
        e = Entity(
            id="1", name="X", entity_type=EntityType.FUNCTION,
            description="handles authentication",
        )
        score = e.matches("authentication")
        self.assertGreater(score, 0.0)

    def test_tag_match(self) -> None:
        e = Entity(
            id="1", name="X", entity_type=EntityType.CONCEPT,
            tags=["security", "auth"],
        )
        score = e.matches("security")
        self.assertGreater(score, 0.0)

    def test_no_match_returns_zero(self) -> None:
        e = Entity(id="1", name="Foo", entity_type=EntityType.FILE)
        self.assertEqual(e.matches("xyz"), 0.0)


class TestQueryResult(unittest.TestCase):
    def test_counts(self) -> None:
        qr = QueryResult(
            entities=[Entity(id="1", name="A", entity_type=EntityType.FILE)],
            relationships=[
                Relationship("1", "2", RelationType.CONTAINS),
            ],
        )
        self.assertEqual(qr.entity_count, 1)
        self.assertEqual(qr.relationship_count, 1)

    def test_empty(self) -> None:
        qr = QueryResult()
        self.assertEqual(qr.entity_count, 0)


class TestKnowledgeGraph(unittest.TestCase):
    def _make_graph(self) -> KnowledgeGraph:
        g = KnowledgeGraph()
        g.add_entity(Entity(id="f1", name="main.py", entity_type=EntityType.FILE))
        g.add_entity(Entity(id="c1", name="UserService", entity_type=EntityType.CLASS))
        g.add_entity(Entity(id="fn1", name="get_user", entity_type=EntityType.FUNCTION))
        g.add_relationship(Relationship("f1", "c1", RelationType.CONTAINS))
        g.add_relationship(Relationship("c1", "fn1", RelationType.DEFINES))
        return g

    def test_add_and_get_entity(self) -> None:
        g = KnowledgeGraph()
        e = Entity(id="x", name="X", entity_type=EntityType.CONCEPT)
        g.add_entity(e)
        self.assertEqual(g.get_entity("x"), e)

    def test_get_missing_entity_returns_none(self) -> None:
        g = KnowledgeGraph()
        self.assertIsNone(g.get_entity("nope"))

    def test_add_relationship_missing_source(self) -> None:
        g = KnowledgeGraph()
        g.add_entity(Entity(id="a", name="A", entity_type=EntityType.FILE))
        with self.assertRaises(KeyError):
            g.add_relationship(Relationship("missing", "a", RelationType.CONTAINS))

    def test_add_relationship_missing_target(self) -> None:
        g = KnowledgeGraph()
        g.add_entity(Entity(id="a", name="A", entity_type=EntityType.FILE))
        with self.assertRaises(KeyError):
            g.add_relationship(Relationship("a", "missing", RelationType.CONTAINS))

    def test_all_entities_and_relationships(self) -> None:
        g = self._make_graph()
        self.assertEqual(len(g.all_entities()), 3)
        self.assertEqual(len(g.all_relationships()), 2)

    def test_neighbors(self) -> None:
        g = self._make_graph()
        neighbors = g.neighbors("c1")
        ids = {n.id for n in neighbors}
        self.assertIn("f1", ids)
        self.assertIn("fn1", ids)

    def test_outgoing_incoming(self) -> None:
        g = self._make_graph()
        out = g.outgoing("f1")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].target_id, "c1")
        inc = g.incoming("c1")
        self.assertEqual(len(inc), 1)
        self.assertEqual(inc[0].source_id, "f1")

    def test_find_by_type(self) -> None:
        g = self._make_graph()
        files = g.find_by_type(EntityType.FILE)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].id, "f1")

    def test_find_by_tag(self) -> None:
        g = KnowledgeGraph()
        g.add_entity(Entity(id="a", name="A", entity_type=EntityType.CONCEPT, tags=["auth"]))
        g.add_entity(Entity(id="b", name="B", entity_type=EntityType.CONCEPT, tags=["db"]))
        self.assertEqual(len(g.find_by_tag("auth")), 1)

    def test_find_related(self) -> None:
        g = self._make_graph()
        related = g.find_related("f1", RelationType.CONTAINS)
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0].id, "c1")

    def test_remove_entity(self) -> None:
        g = self._make_graph()
        self.assertTrue(g.remove_entity("fn1"))
        self.assertIsNone(g.get_entity("fn1"))
        # relationship involving fn1 should be gone
        self.assertEqual(len(g.outgoing("c1")), 0)

    def test_remove_nonexistent_entity(self) -> None:
        g = KnowledgeGraph()
        self.assertFalse(g.remove_entity("nope"))

    def test_shortest_path(self) -> None:
        g = self._make_graph()
        path = g.shortest_path("f1", "fn1")
        self.assertEqual(path, ["f1", "c1", "fn1"])

    def test_shortest_path_same_node(self) -> None:
        g = self._make_graph()
        self.assertEqual(g.shortest_path("f1", "f1"), ["f1"])

    def test_shortest_path_unreachable(self) -> None:
        g = KnowledgeGraph()
        g.add_entity(Entity(id="a", name="A", entity_type=EntityType.FILE))
        g.add_entity(Entity(id="b", name="B", entity_type=EntityType.FILE))
        self.assertEqual(g.shortest_path("a", "b"), [])

    def test_shortest_path_missing_node(self) -> None:
        g = KnowledgeGraph()
        self.assertEqual(g.shortest_path("x", "y"), [])

    def test_subgraph(self) -> None:
        g = self._make_graph()
        result = g.subgraph("f1", depth=1)
        ids = {e.id for e in result.entities}
        self.assertIn("f1", ids)
        self.assertIn("c1", ids)
        self.assertTrue(result.relationship_count > 0)

    def test_subgraph_missing_root(self) -> None:
        g = KnowledgeGraph()
        result = g.subgraph("nope")
        self.assertEqual(result.entity_count, 0)

    def test_subgraph_depth_2(self) -> None:
        g = self._make_graph()
        result = g.subgraph("f1", depth=2)
        ids = {e.id for e in result.entities}
        self.assertIn("fn1", ids)

    def test_stats(self) -> None:
        g = self._make_graph()
        s = g.stats()
        self.assertEqual(s["entities"], 3)
        self.assertEqual(s["relationships"], 2)
        self.assertIn("file", s["entity_types"])
        self.assertIn("contains", s["relationship_types"])


if __name__ == "__main__":
    unittest.main()
