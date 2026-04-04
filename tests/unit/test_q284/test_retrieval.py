"""Tests for lidco.agent_memory.retrieval."""
from __future__ import annotations

import unittest

from lidco.agent_memory.episodic import EpisodicMemory
from lidco.agent_memory.procedural import ProceduralMemory
from lidco.agent_memory.semantic import SemanticMemory2
from lidco.agent_memory.retrieval import MemoryRetrieval, RetrievalResult


class TestMemoryRetrieval(unittest.TestCase):
    def setUp(self):
        self.retrieval = MemoryRetrieval()

    def test_add_source_and_sources(self):
        mem = EpisodicMemory()
        self.retrieval.add_source("ep", mem)
        self.assertEqual(self.retrieval.sources(), ["ep"])

    def test_add_source_empty_name_raises(self):
        with self.assertRaises(ValueError):
            self.retrieval.add_source("", EpisodicMemory())

    def test_retrieve_empty_query(self):
        self.assertEqual(self.retrieval.retrieve(""), [])

    def test_retrieve_from_episodic(self):
        ep = EpisodicMemory()
        ep.record({"description": "Fixed auth bug", "outcome": "success", "strategy": "null check"})
        self.retrieval.add_source("episodic", ep)
        results = self.retrieval.retrieve("auth")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].source, "episodic")
        self.assertIsInstance(results[0], RetrievalResult)

    def test_retrieve_from_procedural(self):
        proc = ProceduralMemory()
        proc.record({"task_type": "refactor", "name": "extract method refactor", "steps": ["identify", "extract"]})
        self.retrieval.add_source("procedural", proc)
        results = self.retrieval.retrieve("refactor")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].source, "procedural")

    def test_retrieve_from_semantic(self):
        sem = SemanticMemory2()
        sem.add_fact({"content": "Python uses GIL for threads"})
        self.retrieval.add_source("semantic", sem)
        results = self.retrieval.retrieve("Python GIL")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].source, "semantic")

    def test_retrieve_top_k(self):
        ep = EpisodicMemory()
        for i in range(10):
            ep.record({"description": f"auth issue {i}", "outcome": "success", "strategy": "fix auth"})
        self.retrieval.add_source("ep", ep)
        results = self.retrieval.retrieve("auth", top_k=3)
        self.assertLessEqual(len(results), 3)

    def test_retrieve_combines_sources(self):
        ep = EpisodicMemory()
        ep.record({"description": "auth login fix", "outcome": "success", "strategy": "token auth"})
        sem = SemanticMemory2()
        sem.add_fact({"content": "auth uses JWT tokens"})
        self.retrieval.add_source("episodic", ep)
        self.retrieval.add_source("semantic", sem)
        results = self.retrieval.retrieve("auth token")
        sources = {r.source for r in results}
        self.assertGreaterEqual(len(sources), 1)

    def test_result_has_score(self):
        ep = EpisodicMemory()
        ep.record({"description": "cache optimization", "outcome": "success", "strategy": "LRU cache"})
        self.retrieval.add_source("ep", ep)
        results = self.retrieval.retrieve("cache")
        self.assertGreater(results[0].score, 0.0)

    def test_result_metadata(self):
        ep = EpisodicMemory()
        ep.record({"description": "test fix", "outcome": "failure", "strategy": "retry"})
        self.retrieval.add_source("ep", ep)
        results = self.retrieval.retrieve("test fix")
        self.assertIn("type", results[0].metadata)
        self.assertEqual(results[0].metadata["outcome"], "failure")

    def test_multiple_sources_list(self):
        self.retrieval.add_source("a", EpisodicMemory())
        self.retrieval.add_source("b", ProceduralMemory())
        self.assertEqual(len(self.retrieval.sources()), 2)


if __name__ == "__main__":
    unittest.main()
