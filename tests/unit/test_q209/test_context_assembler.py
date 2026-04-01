"""Tests for context_assembler module."""
from __future__ import annotations

import unittest

from lidco.understanding.context_assembler import (
    AssemblyResult,
    ContextAssembler,
    ContextEntry,
)


class TestContextEntry(unittest.TestCase):
    def test_frozen(self):
        e = ContextEntry(path="a.py", relevance=0.8)
        with self.assertRaises(AttributeError):
            e.relevance = 0.5  # type: ignore[misc]

    def test_defaults(self):
        e = ContextEntry(path="a.py", relevance=0.8)
        self.assertEqual(e.tokens_estimate, 0)
        self.assertEqual(e.reason, "")


class TestAssemblyResult(unittest.TestCase):
    def test_defaults(self):
        r = AssemblyResult()
        self.assertEqual(r.entries, ())
        self.assertEqual(r.total_tokens, 0)
        self.assertEqual(r.budget_used, 0.0)


class TestContextAssembler(unittest.TestCase):
    def setUp(self):
        self.asm = ContextAssembler(token_budget=1000)

    def test_add_source_and_count(self):
        self.assertEqual(self.asm.source_count(), 0)
        self.asm.add_source("a.py", "some content here", relevance=0.8)
        self.assertEqual(self.asm.source_count(), 1)

    def test_assemble_returns_results(self):
        self.asm.add_source("a.py", "authentication logic code", relevance=0.9)
        self.asm.add_source("b.py", "database connection pool", relevance=0.3)
        result = self.asm.assemble("authentication")
        self.assertIsInstance(result, AssemblyResult)
        self.assertGreater(len(result.entries), 0)
        # Higher relevance first
        if len(result.entries) >= 2:
            self.assertGreaterEqual(result.entries[0].relevance, result.entries[1].relevance)

    def test_assemble_respects_budget(self):
        # Budget is 1000 tokens. Each char ~ 1/4 token.
        # 5000 chars ~ 1250 tokens, exceeds budget
        self.asm.add_source("big.py", "x" * 5000, relevance=0.9)
        self.asm.add_source("small.py", "y" * 100, relevance=0.8)
        result = self.asm.assemble("anything")
        paths = [e.path for e in result.entries]
        self.assertIn("small.py", paths)
        # big.py exceeds budget
        self.assertNotIn("big.py", paths)

    def test_assemble_empty(self):
        result = self.asm.assemble("query")
        self.assertEqual(len(result.entries), 0)

    def test_estimate_tokens(self):
        est = self.asm.estimate_tokens("hello world!!")
        self.assertEqual(est, len("hello world!!") // 4)

    def test_estimate_tokens_minimum_one(self):
        est = self.asm.estimate_tokens("ab")
        self.assertGreaterEqual(est, 1)

    def test_set_budget(self):
        self.asm.set_budget(500)
        self.asm.add_source("a.py", "x" * 2500, relevance=0.9)
        result = self.asm.assemble("test")
        # 2500 chars / 4 = 625 tokens > 500 budget
        self.assertEqual(len(result.entries), 0)

    def test_clear(self):
        self.asm.add_source("a.py", "content", relevance=0.5)
        self.asm.clear()
        self.assertEqual(self.asm.source_count(), 0)


if __name__ == "__main__":
    unittest.main()
