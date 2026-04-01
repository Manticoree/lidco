"""Tests for Q186 CLI commands."""

from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.q186_cmds import register_q186_commands


class _FakeRegistry:
    def __init__(self) -> None:
        self.commands: dict[str, object] = {}

    def register(self, cmd: object) -> None:
        self.commands[cmd.name] = cmd  # type: ignore[attr-defined]


class TestQ186Commands(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = _FakeRegistry()
        register_q186_commands(self.registry)

    def test_all_commands_registered(self) -> None:
        expected = {"review-pipeline", "review-comments", "review-failures", "review-types"}
        self.assertEqual(set(self.registry.commands.keys()), expected)

    def test_review_pipeline_empty(self) -> None:
        handler = self.registry.commands["review-pipeline"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_review_pipeline_with_diff(self) -> None:
        handler = self.registry.commands["review-pipeline"].handler
        result = asyncio.run(handler("except:\n    pass"))
        # Should detect bare except
        self.assertTrue(len(result) > 0)

    def test_review_comments_empty(self) -> None:
        handler = self.registry.commands["review-comments"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_review_comments_with_diff(self) -> None:
        handler = self.registry.commands["review-comments"].handler
        diff = "+++ b/app.py\n@@ -0,0 +1,1 @@\n+# TODO fix later"
        result = asyncio.run(handler(diff))
        self.assertTrue(len(result) > 0)

    def test_review_failures_empty(self) -> None:
        handler = self.registry.commands["review-failures"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_review_failures_with_diff(self) -> None:
        handler = self.registry.commands["review-failures"].handler
        diff = "+++ b/app.py\n@@ -0,0 +1,1 @@\n+except:"
        result = asyncio.run(handler(diff))
        self.assertTrue(len(result) > 0)

    def test_review_types_empty(self) -> None:
        handler = self.registry.commands["review-types"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_review_types_with_diff(self) -> None:
        handler = self.registry.commands["review-types"].handler
        diff = "+++ b/app.py\n@@ -0,0 +1,1 @@\n+def foo(x: Any) -> None:"
        result = asyncio.run(handler(diff))
        self.assertTrue(len(result) > 0)

    def test_review_pipeline_description(self) -> None:
        cmd = self.registry.commands["review-pipeline"]
        self.assertIn("pipeline", cmd.description.lower())

    def test_review_comments_description(self) -> None:
        cmd = self.registry.commands["review-comments"]
        self.assertIn("comment", cmd.description.lower())

    def test_review_failures_description(self) -> None:
        cmd = self.registry.commands["review-failures"]
        self.assertIn("failure", cmd.description.lower())

    def test_review_types_description(self) -> None:
        cmd = self.registry.commands["review-types"]
        self.assertIn("type", cmd.description.lower())


if __name__ == "__main__":
    unittest.main()
