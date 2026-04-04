"""Tests for lidco.agent_memory.semantic."""
from __future__ import annotations

import time
import unittest

from lidco.agent_memory.semantic import SemanticMemory2, Fact


class TestSemanticMemory2(unittest.TestCase):
    def setUp(self):
        self.mem = SemanticMemory2()

    def test_add_fact_returns_fact(self):
        f = self.mem.add_fact({"content": "Python uses GIL"})
        self.assertIsInstance(f, Fact)
        self.assertEqual(f.content, "Python uses GIL")
        self.assertEqual(f.category, "general")

    def test_add_fact_with_category_and_tags(self):
        f = self.mem.add_fact({
            "content": "Use pytest for testing",
            "category": "conventions",
            "tags": ["testing", "python"],
        })
        self.assertEqual(f.category, "conventions")
        self.assertEqual(f.tags, ["testing", "python"])

    def test_add_fact_with_confidence(self):
        f = self.mem.add_fact({"content": "Maybe use async", "confidence": 0.5})
        self.assertAlmostEqual(f.confidence, 0.5)

    def test_add_fact_empty_content_raises(self):
        with self.assertRaises(ValueError):
            self.mem.add_fact({"content": ""})

    def test_query_by_keyword(self):
        self.mem.add_fact({"content": "Python uses GIL for thread safety"})
        self.mem.add_fact({"content": "Redis is fast key-value store"})
        results = self.mem.query("Python GIL")
        self.assertEqual(len(results), 1)
        self.assertIn("GIL", results[0].content)

    def test_query_empty_returns_empty(self):
        self.mem.add_fact({"content": "something"})
        self.assertEqual(self.mem.query(""), [])

    def test_query_includes_tags(self):
        self.mem.add_fact({"content": "Use this library", "tags": ["caching"]})
        results = self.mem.query("caching")
        self.assertEqual(len(results), 1)

    def test_decay_removes_old_facts(self):
        old_time = time.time() - 100 * 86400
        self.mem.add_fact({"content": "old fact", "timestamp": old_time})
        self.mem.add_fact({"content": "new fact"})
        removed = self.mem.decay(30)
        self.assertEqual(removed, 1)
        self.assertEqual(len(self.mem.facts()), 1)
        self.assertEqual(self.mem.facts()[0].content, "new fact")

    def test_decay_zero_days_removes_all_old(self):
        old_time = time.time() - 86400
        self.mem.add_fact({"content": "fact", "timestamp": old_time})
        removed = self.mem.decay(0)
        self.assertEqual(removed, 1)

    def test_decay_no_removals(self):
        self.mem.add_fact({"content": "recent fact"})
        removed = self.mem.decay(30)
        self.assertEqual(removed, 0)

    def test_facts_returns_all(self):
        self.mem.add_fact({"content": "a"})
        self.mem.add_fact({"content": "b"})
        self.assertEqual(len(self.mem.facts()), 2)

    def test_confidence_affects_query_ranking(self):
        self.mem.add_fact({"content": "Python tip low", "confidence": 0.1})
        self.mem.add_fact({"content": "Python tip high", "confidence": 1.0})
        results = self.mem.query("Python tip")
        self.assertEqual(results[0].content, "Python tip high")


if __name__ == "__main__":
    unittest.main()
