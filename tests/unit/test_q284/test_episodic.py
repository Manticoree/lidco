"""Tests for lidco.agent_memory.episodic."""
from __future__ import annotations

import unittest

from lidco.agent_memory.episodic import EpisodicMemory, Episode


class TestEpisodicMemory(unittest.TestCase):
    def setUp(self):
        self.mem = EpisodicMemory()

    def test_record_returns_episode(self):
        ep = self.mem.record({
            "description": "Fixed auth bug",
            "outcome": "success",
            "strategy": "added null check",
        })
        self.assertIsInstance(ep, Episode)
        self.assertEqual(ep.description, "Fixed auth bug")
        self.assertEqual(ep.outcome, "success")
        self.assertEqual(ep.strategy, "added null check")

    def test_record_with_files(self):
        ep = self.mem.record({
            "description": "Refactored parser",
            "outcome": "success",
            "strategy": "extract method",
            "files": ["parser.py", "utils.py"],
        })
        self.assertEqual(ep.files, ["parser.py", "utils.py"])

    def test_record_missing_description_raises(self):
        with self.assertRaises(ValueError):
            self.mem.record({"outcome": "success", "strategy": "x"})

    def test_record_invalid_outcome_raises(self):
        with self.assertRaises(ValueError):
            self.mem.record({"description": "x", "outcome": "unknown", "strategy": "y"})

    def test_record_missing_strategy_raises(self):
        with self.assertRaises(ValueError):
            self.mem.record({"description": "x", "outcome": "success"})

    def test_search_by_keyword(self):
        self.mem.record({"description": "Fixed auth login", "outcome": "success", "strategy": "null check"})
        self.mem.record({"description": "Added tests for cache", "outcome": "failure", "strategy": "mocking"})
        results = self.mem.search("auth")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].description, "Fixed auth login")

    def test_search_empty_query(self):
        self.mem.record({"description": "x", "outcome": "success", "strategy": "y"})
        self.assertEqual(self.mem.search(""), [])

    def test_by_outcome(self):
        self.mem.record({"description": "a", "outcome": "success", "strategy": "s"})
        self.mem.record({"description": "b", "outcome": "failure", "strategy": "s"})
        self.mem.record({"description": "c", "outcome": "success", "strategy": "s"})
        self.assertEqual(len(self.mem.by_outcome("success")), 2)
        self.assertEqual(len(self.mem.by_outcome("failure")), 1)

    def test_recent_returns_newest_first(self):
        import time
        e1 = self.mem.record({"description": "old", "outcome": "success", "strategy": "s", "timestamp": 1.0})
        e2 = self.mem.record({"description": "new", "outcome": "success", "strategy": "s", "timestamp": 2.0})
        recent = self.mem.recent(1)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].description, "new")

    def test_recent_default(self):
        for i in range(10):
            self.mem.record({"description": f"ep{i}", "outcome": "success", "strategy": "s"})
        self.assertEqual(len(self.mem.recent()), 5)

    def test_all(self):
        self.mem.record({"description": "a", "outcome": "success", "strategy": "s"})
        self.assertEqual(len(self.mem.all()), 1)

    def test_episode_frozen(self):
        ep = self.mem.record({"description": "x", "outcome": "success", "strategy": "y"})
        with self.assertRaises(AttributeError):
            ep.description = "mutated"


if __name__ == "__main__":
    unittest.main()
