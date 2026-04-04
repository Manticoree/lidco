"""Tests for lidco.cli.commands.q284_cmds."""
from __future__ import annotations

import asyncio
import unittest

import lidco.cli.commands.q284_cmds as q284_mod
from lidco.cli.commands.q284_cmds import register_q284_commands


class _FakeRegistry:
    """Minimal registry that captures registered commands."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ284Commands(unittest.TestCase):
    def setUp(self):
        # Reset module-level state between tests.
        q284_mod._state.clear()
        self.registry = _FakeRegistry()
        register_q284_commands(self.registry)

    def test_commands_registered(self):
        names = set(self.registry.commands.keys())
        self.assertIn("episodic-memory", names)
        self.assertIn("procedural-memory", names)
        self.assertIn("semantic-memory", names)
        self.assertIn("memory-retrieve", names)

    def test_episodic_record(self):
        handler = self.registry.commands["episodic-memory"].handler
        result = asyncio.run(handler('record "fixed bug" success "null check"'))
        self.assertIn("Recorded episode", result)

    def test_episodic_recent_empty(self):
        handler = self.registry.commands["episodic-memory"].handler
        result = asyncio.run(handler("recent"))
        self.assertIn("No episodes", result)

    def test_episodic_search_no_query(self):
        handler = self.registry.commands["episodic-memory"].handler
        result = asyncio.run(handler("search"))
        self.assertIn("Usage", result)

    def test_episodic_by_outcome(self):
        handler = self.registry.commands["episodic-memory"].handler
        asyncio.run(handler('record "task" success "strategy"'))
        result = asyncio.run(handler("by-outcome success"))
        self.assertIn("1 success episode", result)

    def test_episodic_usage(self):
        handler = self.registry.commands["episodic-memory"].handler
        result = asyncio.run(handler("unknown"))
        self.assertIn("Usage", result)

    def test_procedural_record(self):
        handler = self.registry.commands["procedural-memory"].handler
        result = asyncio.run(handler('record refactor "extract method" identify extract'))
        self.assertIn("Recorded procedure", result)
        self.assertIn("2 steps", result)

    def test_procedural_find_empty(self):
        handler = self.registry.commands["procedural-memory"].handler
        result = asyncio.run(handler("find bugfix"))
        self.assertIn("No matching", result)

    def test_procedural_generalize_empty(self):
        handler = self.registry.commands["procedural-memory"].handler
        result = asyncio.run(handler("generalize"))
        self.assertIn("No generalizable", result)

    def test_semantic_add(self):
        handler = self.registry.commands["semantic-memory"].handler
        result = asyncio.run(handler('add "Python uses GIL" architecture'))
        self.assertIn("Added fact", result)
        self.assertIn("architecture", result)

    def test_semantic_list_empty(self):
        handler = self.registry.commands["semantic-memory"].handler
        result = asyncio.run(handler("list"))
        self.assertIn("No facts", result)

    def test_semantic_query_no_query(self):
        handler = self.registry.commands["semantic-memory"].handler
        result = asyncio.run(handler("query"))
        self.assertIn("Usage", result)

    def test_semantic_decay(self):
        handler = self.registry.commands["semantic-memory"].handler
        result = asyncio.run(handler("decay 30"))
        self.assertIn("Removed 0", result)

    def test_memory_retrieve_no_args(self):
        handler = self.registry.commands["memory-retrieve"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_memory_retrieve_with_data(self):
        ep_handler = self.registry.commands["episodic-memory"].handler
        asyncio.run(ep_handler('record "auth fix" success "token validation"'))
        handler = self.registry.commands["memory-retrieve"].handler
        result = asyncio.run(handler("auth"))
        # Should find the episodic entry
        self.assertIn("result", result.lower())


if __name__ == "__main__":
    unittest.main()
