"""Tests for lidco.llm.model_aliases — Q162 Task 925."""
from __future__ import annotations

import json
import os
import tempfile
import unittest

from lidco.llm.model_aliases import ModelAliasRegistry


class TestModelAliasRegistry(unittest.TestCase):
    def test_default_aliases(self) -> None:
        r = ModelAliasRegistry()
        aliases = r.list()
        self.assertEqual(aliases["s"], "anthropic/claude-sonnet-4-6")
        self.assertEqual(aliases["o"], "anthropic/claude-opus-4-6")
        self.assertEqual(aliases["h"], "anthropic/claude-haiku-4-5")

    def test_custom_aliases(self) -> None:
        r = ModelAliasRegistry(aliases={"g": "openai/gpt-4o"})
        self.assertEqual(r.list(), {"g": "openai/gpt-4o"})

    def test_add(self) -> None:
        r = ModelAliasRegistry(aliases={})
        r.add("fast", "anthropic/claude-haiku-4-5")
        self.assertEqual(r.resolve("fast"), "anthropic/claude-haiku-4-5")

    def test_remove_existing(self) -> None:
        r = ModelAliasRegistry()
        self.assertTrue(r.remove("s"))
        self.assertNotIn("s", r.list())

    def test_remove_missing(self) -> None:
        r = ModelAliasRegistry(aliases={})
        self.assertFalse(r.remove("nope"))

    def test_resolve_alias(self) -> None:
        r = ModelAliasRegistry()
        self.assertEqual(r.resolve("s"), "anthropic/claude-sonnet-4-6")

    def test_resolve_passthrough(self) -> None:
        r = ModelAliasRegistry()
        self.assertEqual(r.resolve("openai/gpt-4o"), "openai/gpt-4o")

    def test_list_returns_copy(self) -> None:
        r = ModelAliasRegistry()
        d = r.list()
        d["x"] = "y"
        self.assertNotIn("x", r.list())

    def test_save_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "aliases.json")
            r1 = ModelAliasRegistry(aliases={"a": "model-a"})
            r1.save(path)

            r2 = ModelAliasRegistry(aliases={})
            r2.load(path)
            self.assertEqual(r2.resolve("a"), "model-a")

    def test_load_nonexistent(self) -> None:
        r = ModelAliasRegistry(aliases={"x": "y"})
        r.load("/nonexistent/path.json")
        # Should keep existing aliases
        self.assertEqual(r.resolve("x"), "y")

    def test_save_creates_parent_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "sub", "deep", "aliases.json")
            r = ModelAliasRegistry(aliases={"k": "v"})
            r.save(path)
            self.assertTrue(os.path.isfile(path))

    def test_immutable_add(self) -> None:
        """add() should not mutate existing dict reference."""
        r = ModelAliasRegistry(aliases={"a": "1"})
        old = r.list()
        r.add("b", "2")
        new = r.list()
        self.assertNotIn("b", old)
        self.assertIn("b", new)

    def test_immutable_remove(self) -> None:
        r = ModelAliasRegistry(aliases={"a": "1", "b": "2"})
        old = r.list()
        r.remove("a")
        new = r.list()
        self.assertIn("a", old)
        self.assertNotIn("a", new)

    def test_load_invalid_json_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "bad.json")
            with open(path, "w") as f:
                json.dump([1, 2, 3], f)
            r = ModelAliasRegistry(aliases={"x": "y"})
            r.load(path)
            # Non-dict JSON should not replace aliases
            self.assertEqual(r.resolve("x"), "y")


if __name__ == "__main__":
    unittest.main()
