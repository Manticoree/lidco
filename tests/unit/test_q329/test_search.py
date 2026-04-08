"""Tests for Q329 — KnowledgeSearch."""
from __future__ import annotations

import unittest

from lidco.knowledge.graph import (
    Entity,
    EntityType,
    KnowledgeGraph,
    Relationship,
    RelationType,
)
from lidco.knowledge.search import (
    KnowledgeSearch,
    SearchHit,
    SearchResult,
    _tokenize,
)


class TestTokenize(unittest.TestCase):
    def test_basic(self) -> None:
        tokens = _tokenize("how does auth work?")
        self.assertIn("auth", tokens)
        self.assertNotIn("how", tokens)
        self.assertNotIn("does", tokens)

    def test_empty(self) -> None:
        self.assertEqual(_tokenize(""), [])

    def test_only_stop_words(self) -> None:
        self.assertEqual(_tokenize("the is a an"), [])


class TestSearchHit(unittest.TestCase):
    def test_fields(self) -> None:
        e = Entity(id="1", name="Foo", entity_type=EntityType.CLASS)
        hit = SearchHit(entity=e, score=0.8, context="ctx")
        self.assertEqual(hit.score, 0.8)
        self.assertEqual(hit.context, "ctx")


class TestSearchResult(unittest.TestCase):
    def test_hit_count(self) -> None:
        r = SearchResult(query="q", hits=[
            SearchHit(entity=Entity(id="1", name="A", entity_type=EntityType.FILE), score=0.5),
        ])
        self.assertEqual(r.hit_count, 1)

    def test_top_hit(self) -> None:
        r = SearchResult(query="q", hits=[
            SearchHit(entity=Entity(id="1", name="A", entity_type=EntityType.FILE), score=0.9),
            SearchHit(entity=Entity(id="2", name="B", entity_type=EntityType.FILE), score=0.3),
        ])
        self.assertIsNotNone(r.top_hit)
        self.assertEqual(r.top_hit.entity.name, "A")

    def test_top_hit_empty(self) -> None:
        r = SearchResult(query="q")
        self.assertIsNone(r.top_hit)

    def test_summary_no_results(self) -> None:
        r = SearchResult(query="xyz")
        self.assertIn("No results", r.summary())

    def test_summary_with_results(self) -> None:
        r = SearchResult(query="auth", hits=[
            SearchHit(
                entity=Entity(id="1", name="AuthService", entity_type=EntityType.CLASS,
                              description="Handles auth"),
                score=0.9,
            ),
        ])
        s = r.summary()
        self.assertIn("AuthService", s)
        self.assertIn("0.90", s)


def _build_graph() -> KnowledgeGraph:
    g = KnowledgeGraph()
    g.add_entity(Entity(
        id="auth", name="AuthService", entity_type=EntityType.CLASS,
        description="Handles user authentication", tags=["security", "auth"],
    ))
    g.add_entity(Entity(
        id="db", name="DatabasePool", entity_type=EntityType.CLASS,
        description="Database connection pool", tags=["database"],
    ))
    g.add_entity(Entity(
        id="singleton", name="SingletonPattern", entity_type=EntityType.PATTERN,
        description="Singleton design pattern detected",
    ))
    g.add_entity(Entity(
        id="rule1", name="PasswordLength", entity_type=EntityType.RULE,
        description="Password must be at least 8 characters",
    ))
    g.add_relationship(Relationship("auth", "db", RelationType.DEPENDS_ON))
    return g


class TestKnowledgeSearch(unittest.TestCase):
    def test_search_by_name(self) -> None:
        g = _build_graph()
        search = KnowledgeSearch(g)
        result = search.search("AuthService")
        self.assertGreater(result.hit_count, 0)
        self.assertEqual(result.hits[0].entity.id, "auth")

    def test_search_by_description(self) -> None:
        g = _build_graph()
        search = KnowledgeSearch(g)
        result = search.search("authentication")
        self.assertGreater(result.hit_count, 0)

    def test_search_by_tag(self) -> None:
        g = _build_graph()
        search = KnowledgeSearch(g)
        result = search.search("security")
        self.assertGreater(result.hit_count, 0)
        self.assertEqual(result.hits[0].entity.id, "auth")

    def test_search_no_results(self) -> None:
        g = _build_graph()
        search = KnowledgeSearch(g)
        result = search.search("quantum computing")
        self.assertEqual(result.hit_count, 0)

    def test_search_limit(self) -> None:
        g = _build_graph()
        search = KnowledgeSearch(g)
        result = search.search("service pool pattern", limit=2)
        self.assertLessEqual(result.hit_count, 2)

    def test_search_stop_words_only(self) -> None:
        g = _build_graph()
        search = KnowledgeSearch(g)
        result = search.search("the is a")
        self.assertEqual(result.hit_count, 0)

    def test_answer_found(self) -> None:
        g = _build_graph()
        search = KnowledgeSearch(g)
        ans = search.answer("how does auth work?")
        self.assertIn("AuthService", ans)

    def test_answer_not_found(self) -> None:
        g = _build_graph()
        search = KnowledgeSearch(g)
        ans = search.answer("quantum entanglement")
        self.assertIn("don't have information", ans)

    def test_answer_includes_related(self) -> None:
        g = _build_graph()
        search = KnowledgeSearch(g)
        ans = search.answer("AuthService")
        self.assertIn("Related", ans)

    def test_find_by_concept_filters_type(self) -> None:
        g = _build_graph()
        search = KnowledgeSearch(g)
        result = search.find_by_concept("singleton")
        for hit in result.hits:
            self.assertIn(hit.entity.entity_type, (
                EntityType.CONCEPT, EntityType.PATTERN, EntityType.RULE,
            ))

    def test_find_by_concept_no_match(self) -> None:
        g = _build_graph()
        search = KnowledgeSearch(g)
        result = search.find_by_concept("xyz")
        self.assertEqual(result.hit_count, 0)

    def test_related_entities_populated(self) -> None:
        g = _build_graph()
        search = KnowledgeSearch(g)
        result = search.search("AuthService")
        if result.hits:
            # auth -> db via depends_on
            rel_ids = {e.id for e in result.hits[0].related_entities}
            self.assertIn("db", rel_ids)

    def test_context_string(self) -> None:
        g = _build_graph()
        search = KnowledgeSearch(g)
        result = search.search("database")
        self.assertGreater(result.hit_count, 0)
        self.assertTrue(len(result.hits[0].context) > 0)


if __name__ == "__main__":
    unittest.main()
